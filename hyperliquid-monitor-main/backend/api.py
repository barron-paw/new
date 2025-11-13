"""REST API surface for Hyperliquid monitoring data."""
from __future__ import annotations

import logging
import os
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.header import Header
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Literal

import bcrypt
import jwt
import requests
import schedule
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from .database import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_payment_hash,
    get_user_config,
    list_users,
    update_user,
    upsert_user_config,
    upsert_email_verification,
    consume_email_verification,
    get_binance_follow_config,
    upsert_binance_follow_config,
    get_wecom_config,
    upsert_wecom_config,
)
from .monitor_positions import (
    CONFIGURED_ADDRESSES,
    _calculate_entry_price,
    _calculate_leverage,
    _extract_account_value,
    _extract_tx_hash,
    _safe_float,
    _safe_int,
    calculate_position_metrics,
    get_current_prices,
    get_positions,
    get_trade_history,
    load_position_state,
)
from .monitor_service import (
    configure_user_monitor,
    initialise_monitors_from_db,
    shutdown_monitors,
)
from .binance_follow_service import (
    configure_user_follow as configure_binance_follow,
    initialise_followers_from_db,
    shutdown_followers,
)


JWT_SECRET = os.getenv("JWT_SECRET", "hyperliquid-monitor-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))

BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
BSCSCAN_BASE_URL = os.getenv("BSCSCAN_BASE_URL", "https://api.bscscan.com/api")
USDT_CONTRACT = os.getenv("USDT_CONTRACT", "0x55d398326f99059ff775485246999027b3197955").lower()
USDT_DECIMALS = int(os.getenv("USDT_DECIMALS", "18"))
PAYMENT_TARGET_ADDRESS = os.getenv("PAYMENT_TARGET_ADDRESS", "0xa0191ab9cad3dae4ce390d633c6c467da0ca975d").lower()
SUBSCRIPTION_PRICE_USDT = Decimal(os.getenv("SUBSCRIPTION_PRICE_USDT", "7.9"))
SUBSCRIPTION_DURATION_DAYS = int(os.getenv("SUBSCRIPTION_DURATION_DAYS", "30"))
REMINDER_LEAD_DAYS = int(os.getenv("SUBSCRIPTION_REMINDER_DAYS", "1"))
REMINDER_TIME = os.getenv("SUBSCRIPTION_REMINDER_TIME", "09:00")

DEFAULT_TELEGRAM_BOT_TOKEN = os.getenv("DEFAULT_TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_TELEGRAM_BOT_USERNAME = os.getenv("DEFAULT_TELEGRAM_BOT_USERNAME", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME or "")
EMAIL_ENABLED = bool(SMTP_USERNAME and SMTP_PASSWORD)

TOKEN_MULTIPLIER = Decimal(10) ** USDT_DECIMALS
REQUIRED_AMOUNT_WEI = int((SUBSCRIPTION_PRICE_USDT * TOKEN_MULTIPLIER).to_integral_value())

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
_scheduler_started = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": _now() + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _serialize_user(record: Dict[str, Any]) -> Dict[str, Any]:
    trial_end = _parse_iso(record.get("trial_end"))
    subscription_end = _parse_iso(record.get("subscription_end"))
    now = _now()
    trial_active = bool(trial_end and now <= trial_end)
    subscription_active = bool(subscription_end and now <= subscription_end)
    return {
        "email": record["email"],
        "trial_end": trial_end.isoformat() if trial_end else None,
        "subscription_end": subscription_end.isoformat() if subscription_end else None,
        "trial_active": trial_active,
        "subscription_active": subscription_active,
        "can_access_monitor": bool(trial_active or subscription_active),
    }


def _require_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.PyJWTError as exc:  # pragma: no cover - generic decode error
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _ensure_monitor_access(user: Dict[str, Any]) -> Dict[str, Any]:
    info = _serialize_user(user)
    if info["can_access_monitor"]:
        return info
    raise HTTPException(status_code=402, detail="Subscription or trial required to access monitor configuration")


def _build_binance_response(record: Dict[str, Any]) -> BinanceFollowConfigResponse:
    mode = (record.get("mode") or "fixed").lower()
    if mode not in {"fixed", "percentage"}:
        mode = "fixed"
    return BinanceFollowConfigResponse(
        enabled=bool(record.get("enabled")),
        wallet_address=(record.get("wallet_address") or None),
        mode=mode,
        amount=float(record.get("amount") or 0.0),
        stop_loss_amount=float(record.get("stop_loss_amount") or 0.0),
        max_position=float(record.get("max_position") or 0.0),
        min_order_size=float(record.get("min_order_size") or 0.0),
        has_api_key=bool(record.get("api_key")),
        has_api_secret=bool(record.get("api_secret")),
        baseline_balance=record.get("baseline_balance"),
        status=record.get("status"),
        stop_reason=record.get("stop_reason"),
    )


def _build_wecom_response(record: Dict[str, Any]) -> "WecomConfigResponse":
    mentions = record.get("mentions") or []
    if isinstance(mentions, str):
        mentions = [item for item in mentions.split(",") if item]
    return WecomConfigResponse(
        enabled=bool(record.get("enabled")),
        webhook_url=record.get("webhook_url"),
        mentions=list(mentions),
    )


class PositionPayload(BaseModel):
    coin: str
    side: str
    size: float
    entry_price: Optional[float] = Field(None, alias="entryPrice")
    mark_price: Optional[float] = Field(None, alias="markPrice")
    position_value: float = Field(..., alias="positionValue")
    margin_used: Optional[float] = Field(None, alias="marginUsed")
    liquidation_price: Optional[float] = Field(None, alias="liquidationPrice")
    leverage: Optional[float]
    unrealized_pnl: Optional[float] = Field(None, alias="unrealizedPnl")
    pnl_percent: Optional[float] = Field(None, alias="pnlPercent")
    funding_all_time: Optional[float] = Field(None, alias="fundingAllTime")
    funding_since_open: Optional[float] = Field(None, alias="fundingSinceOpen")
    updated_at: int = Field(..., alias="updatedAt")

    class Config:
        populate_by_name = True


class WalletSummaryPayload(BaseModel):
    address: str
    balance: float
    withdrawable: Optional[float]
    equity: Optional[float]
    total_position_value: float = Field(..., alias="totalPositionValue")
    timestamp: int
    positions: List[PositionPayload]

    class Config:
        populate_by_name = True


class FillPayload(BaseModel):
    coin: str
    side: str
    price: float
    size: float
    time_ms: int = Field(..., alias="timeMs")
    start_position: Optional[float] = Field(None, alias="startPosition")
    end_position: Optional[float] = Field(None, alias="endPosition")
    tx_hash: str = Field(..., alias="txHash")

    class Config:
        populate_by_name = True


class FillListPayload(BaseModel):
    address: str
    count: int
    items: List[FillPayload]


class WalletListPayload(BaseModel):
    wallets: List[str]
    count: int


class WalletMetricsPayload(BaseModel):
    address: str
    summary: WalletSummaryPayload
    fills: FillListPayload
    per_coin: Dict[str, Dict[str, float]] = Field(..., alias="perCoin")

    class Config:
        populate_by_name = True


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    verification_code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthToken(BaseModel):
    token: str


class VerificationRequest(BaseModel):
    email: EmailStr


class UserInfo(BaseModel):
    email: EmailStr
    trial_end: Optional[str]
    subscription_end: Optional[str]
    trial_active: bool
    subscription_active: bool
    can_access_monitor: bool


class AuthResponse(BaseModel):
    token: str
    user: UserInfo


class PaymentVerificationRequest(BaseModel):
    tx_hash: str = Field(..., alias="txHash")


class MonitorConfig(BaseModel):
    telegram_bot_token: Optional[str] = Field(None, alias="telegramBotToken")
    telegram_chat_id: Optional[str] = Field(None, alias="telegramChatId")
    wallet_addresses: List[str] = Field(default_factory=list, alias="walletAddresses")
    language: str = Field("zh", alias="language")
    uses_default_bot: bool = Field(False, alias="usesDefaultBot")
    default_bot_username: Optional[str] = Field(None, alias="defaultBotUsername")

    class Config:
        populate_by_name = True


class BinanceFollowConfigResponse(BaseModel):
    enabled: bool = False
    wallet_address: Optional[str] = Field(None, alias="walletAddress")
    mode: Literal["fixed", "percentage"] = "fixed"
    amount: float = 0.0
    stop_loss_amount: float = Field(0.0, alias="stopLossAmount")
    max_position: float = Field(0.0, alias="maxPosition")
    min_order_size: float = Field(0.0, alias="minOrderSize")
    has_api_key: bool = Field(False, alias="hasApiKey")
    has_api_secret: bool = Field(False, alias="hasApiSecret")
    baseline_balance: Optional[float] = Field(None, alias="baselineBalance")
    status: Optional[str] = Field(None, alias="status")
    stop_reason: Optional[str] = Field(None, alias="stopReason")

    class Config:
        populate_by_name = True


class BinanceFollowConfigRequest(BaseModel):
    enabled: bool = False
    wallet_address: Optional[str] = Field(None, alias="walletAddress")
    mode: Literal["fixed", "percentage"] = "fixed"
    amount: float = 0.0
    stop_loss_amount: float = Field(0.0, alias="stopLossAmount")
    max_position: float = Field(0.0, alias="maxPosition")
    min_order_size: float = Field(0.0, alias="minOrderSize")
    api_key: Optional[str] = Field(None, alias="apiKey")
    api_secret: Optional[str] = Field(None, alias="apiSecret")
    reset_credentials: bool = Field(False, alias="resetCredentials")

    class Config:
        populate_by_name = True


class WecomConfigResponse(BaseModel):
    enabled: bool = False
    webhook_url: Optional[str] = Field(None, alias="webhookUrl")
    mentions: List[str] = Field(default_factory=list, alias="mentions")

    class Config:
        populate_by_name = True


class WecomConfigRequest(BaseModel):
    enabled: bool = False
    webhook_url: Optional[str] = Field(None, alias="webhookUrl")
    mentions: List[str] = Field(default_factory=list, alias="mentions")

    class Config:
        populate_by_name = True


def _format_side(size: float) -> str:
    if size > 0:
        return "long"
    if size < 0:
        return "short"
    return "flat"


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _build_position_payload(position: Dict[str, Any], mark_prices: Dict[str, float]) -> PositionPayload:
    coin = position.get("coin", "")
    size = _safe_float(position.get("szi"))
    position_value = abs(_safe_float(position.get("positionValue")))
    entry_price = _calculate_entry_price(position)
    mark_price = _safe_float(mark_prices.get(coin))
    margin_used = _safe_float(position.get("marginUsed")) or None
    leverage = _calculate_leverage(position)
    liquidation_price = (_safe_float(position.get("liquidationPx")) or None)
    pnl = _safe_float(position.get("unrealizedPnl")) or None
    pnl_percent: Optional[float] = None
    if entry_price > 0 and abs(size) > 0:
        pnl_percent = ((pnl or 0.0) / (entry_price * abs(size))) * 100
    funding = position.get("cumFunding") or {}
    updated_at = int(time.time() * 1000)

    return PositionPayload(
        coin=coin,
        side=_format_side(size),
        size=size,
        entryPrice=entry_price if entry_price > 0 else None,
        markPrice=mark_price if mark_price > 0 else None,
        positionValue=position_value,
        marginUsed=margin_used,
        liquidationPrice=liquidation_price,
        leverage=leverage,
        unrealizedPnl=pnl,
        pnlPercent=pnl_percent,
        fundingAllTime=_safe_float(funding.get("allTime")) or None,
        fundingSinceOpen=_safe_float(funding.get("sinceOpen")) or None,
        updatedAt=updated_at,
    )


def _compose_wallet_summary(address: str) -> WalletSummaryPayload:
    try:
        user_state = get_positions(address)
    except Exception as exc:  # pragma: no cover - network layer
        raise HTTPException(status_code=502, detail=f"Failed to fetch positions for {address}") from exc

    positions_payload: List[PositionPayload] = []
    prices: Dict[str, float] = {}
    try:
        prices = get_current_prices()
    except Exception:  # pragma: no cover - network layer
        prices = {}

    positions_raw = user_state.get("assetPositions", []) or []
    for entry in positions_raw:
        position = entry.get("position", {})
        if not position:
            continue
        positions_payload.append(_build_position_payload(position, prices))

    balance = _extract_account_value(user_state)
    withdrawable = _safe_float(user_state.get("withdrawable")) or None
    margin_summary = user_state.get("marginSummary") or {}
    equity = _safe_float(margin_summary.get("accountValue")) or None
    total_position_value = sum(item.position_value for item in positions_payload)

    timestamp = int(time.time() * 1000)

    return WalletSummaryPayload(
        address=address,
        balance=balance,
        withdrawable=withdrawable,
        equity=equity,
        totalPositionValue=total_position_value,
        timestamp=timestamp,
        positions=positions_payload,
    )


def _compose_fills(
    address: str,
    limit: int,
    fills: Optional[List[Dict[str, Any]]] = None,
) -> FillListPayload:
    try:
        fills_data = fills if fills is not None else get_trade_history(address)
    except Exception as exc:  # pragma: no cover - network layer
        raise HTTPException(status_code=502, detail=f"Failed to fetch fills for {address}") from exc

    sorted_fills = sorted(fills_data, key=lambda item: _safe_int(item.get("time")), reverse=True)

    payload: List[FillPayload] = []
    for fill in sorted_fills[:limit]:
        coin = fill.get("coin", "")
        price = _safe_float(fill.get("px"))
        size = _safe_float(fill.get("sz"))
        side_raw = str(fill.get("side", "")).upper()
        side = "buy" if side_raw == "B" else "sell" if side_raw == "A" else side_raw
        time_ms = _safe_int(fill.get("time"))
        start_position = _safe_float(fill.get("startPosition")) if fill.get("startPosition") is not None else None
        end_position = _safe_float(fill.get("endPosition")) if fill.get("endPosition") is not None else None
        tx_hash = _extract_tx_hash(fill)

        payload.append(
            FillPayload(
                coin=coin,
                side=side,
                price=price,
                size=size,
                timeMs=time_ms,
                startPosition=start_position,
                endPosition=end_position,
                txHash=tx_hash,
            )
        )

    return FillListPayload(address=address, count=len(payload), items=payload)


def _list_known_wallets() -> List[str]:
    state = load_position_state()
    state_wallets = list(state.keys())
    configured = list(CONFIGURED_ADDRESSES)
    merged = sorted({*(wallet for wallet in state_wallets if wallet), *(wallet for wallet in configured if wallet)})
    return merged


app = FastAPI(title="Hyperliquid Monitor API", version="0.1.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("API_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    _start_scheduler()
    initialise_monitors_from_db()
    initialise_followers_from_db()


@app.on_event("shutdown")
def shutdown_event() -> None:
    shutdown_monitors()
    shutdown_followers()


@app.get("/api/health")
def healthcheck() -> Dict[str, Any]:
    return {"status": "ok", "timestamp": int(time.time() * 1000)}


@app.get("/api/wallets", response_model=WalletListPayload)
@app.get("/wallets", response_model=WalletListPayload)
def list_wallets() -> WalletListPayload:
    wallets = _list_known_wallets()
    return WalletListPayload(wallets=wallets, count=len(wallets))


@app.get("/api/wallets/{address}", response_model=WalletSummaryPayload)
@app.get("/wallets/{address}", response_model=WalletSummaryPayload)
def wallet_summary(address: str) -> WalletSummaryPayload:
    return _compose_wallet_summary(address)


@app.get("/api/wallets/{address}/positions", response_model=WalletSummaryPayload)
@app.get("/wallets/{address}/positions", response_model=WalletSummaryPayload)
def wallet_positions(address: str) -> WalletSummaryPayload:
    return wallet_summary(address)


@app.get("/api/wallets/{address}/fills", response_model=FillListPayload)
@app.get("/wallets/{address}/fills", response_model=FillListPayload)
def wallet_fills(address: str, limit: int = Query(50, ge=1, le=200)) -> FillListPayload:
    return _compose_fills(address, limit)


@app.get("/api/wallets/{address}/metrics", response_model=WalletMetricsPayload)
@app.get("/wallets/{address}/metrics", response_model=WalletMetricsPayload)
def wallet_metrics(address: str) -> WalletMetricsPayload:
    summary = wallet_summary(address)
    try:
        fills_raw = get_trade_history(address)
    except Exception as exc:  # pragma: no cover - network layer
        raise HTTPException(status_code=502, detail=f"Failed to fetch fills for {address}") from exc

    fills_payload = _compose_fills(address, limit=200, fills=fills_raw)
    per_coin: Dict[str, Dict[str, float]] = {}
    for position in summary.positions:
        metrics = calculate_position_metrics(position.coin, fills_raw)
        per_coin[position.coin] = metrics

    return WalletMetricsPayload(
        address=address,
        summary=summary,
        fills=fills_payload,
        perCoin=per_coin,
    )


@app.post("/api/auth/request_verification")
def request_email_verification(payload: VerificationRequest) -> Dict[str, str]:
    email = payload.email.lower()
    code = _generate_verification_code()
    expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    upsert_email_verification(email, code, expires_at)
    subject = "Hyperliquid Monitor 邮箱验证码"
    body = (
        "您好！\n\n您的邮箱验证码为：\n\n"
        f"    {code}\n\n验证码 15 分钟内有效，请勿泄露给他人。"
    )
    _send_email(email, subject, body)
    return {"detail": "Verification code sent"}


@app.post("/api/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    email = payload.email.lower()
    if not consume_email_verification(email, payload.verification_code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_record = create_user(email, password_hash, TRIAL_DAYS)
    token = _create_access_token(user_record["id"], user_record["email"])
    return AuthResponse(token=token, user=UserInfo(**_serialize_user(user_record)))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user_record = get_user_by_email(payload.email.lower())
    if not user_record or not bcrypt.checkpw(payload.password.encode("utf-8"), user_record["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _create_access_token(user_record["id"], user_record["email"])
    return AuthResponse(token=token, user=UserInfo(**_serialize_user(user_record)))


@app.get("/api/auth/me", response_model=UserInfo)
def me(current_user: Dict[str, Any] = Depends(_require_current_user)) -> UserInfo:
    return UserInfo(**_serialize_user(current_user))


@app.post("/api/subscription/verify", response_model=UserInfo)
def verify_subscription(
    payload: PaymentVerificationRequest,
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> UserInfo:
    tx_hash = payload.tx_hash.lower()
    if current_user.get("last_payment_hash") == tx_hash:
        return UserInfo(**_serialize_user(current_user))

    existing_owner = get_user_by_payment_hash(tx_hash)
    if existing_owner and existing_owner["id"] != current_user["id"]:
        raise HTTPException(status_code=400, detail="Transaction hash already used by another account")

    payment_data = _verify_payment_on_chain(tx_hash)
    logger.info("Validated subscription payment from %s for tx %s", payment_data.get("from_address"), tx_hash)
    now = _now()
    subscription_end = _parse_iso(current_user.get("subscription_end"))
    if subscription_end and subscription_end > now:
        new_end = subscription_end + timedelta(days=SUBSCRIPTION_DURATION_DAYS)
    else:
        new_end = now + timedelta(days=SUBSCRIPTION_DURATION_DAYS)

    update_user(
        current_user["id"],
        subscription_end=new_end.isoformat(),
        last_payment_hash=tx_hash,
        last_reminder_at=None,
    )
    refreshed = get_user_by_id(current_user["id"])
    if refreshed and EMAIL_ENABLED:
        body = (
            "您的 Hyperliquid Monitor 订阅支付已确认。\n\n"
            f"交易哈希：{tx_hash}\n有效期至：{new_end.isoformat()}。感谢您的支持！"
        )
        _send_email(refreshed["email"], "Hyperliquid Monitor 订阅已激活", body)

    return UserInfo(**_serialize_user(refreshed or current_user))


@app.get("/api/config", response_model=MonitorConfig)
def get_monitor_config(current_user: Dict[str, Any] = Depends(_require_current_user)) -> MonitorConfig:
    _ensure_monitor_access(current_user)
    stored = get_user_config(current_user["id"])
    uses_default = not stored.get("telegram_bot_token") and bool(DEFAULT_TELEGRAM_BOT_TOKEN)
    return MonitorConfig(
        telegram_bot_token=None if uses_default else stored.get("telegram_bot_token"),
        telegram_chat_id=stored.get("telegram_chat_id"),
        wallet_addresses=stored.get("wallet_addresses", []),
        language=stored.get("language", "zh"),
        uses_default_bot=uses_default,
        default_bot_username=DEFAULT_TELEGRAM_BOT_USERNAME or None,
    )


@app.post("/api/config", response_model=MonitorConfig)
def update_monitor_config(
    payload: MonitorConfig,
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> MonitorConfig:
    _ensure_monitor_access(current_user)
    wallets = [addr.strip() for addr in payload.wallet_addresses if addr.strip()]
    language = (payload.language or "zh").lower()
    if language not in {"zh", "en"}:
        language = "zh"
    record = upsert_user_config(
        current_user["id"],
        (payload.telegram_bot_token or "").strip() or None,
        (payload.telegram_chat_id or "").strip() or None,
        wallets,
        language,
    )
    effective_token = record.get("telegram_bot_token") or DEFAULT_TELEGRAM_BOT_TOKEN or None
    configure_user_monitor(
        current_user["id"],
        telegram_bot_token=effective_token,
        telegram_chat_id=record.get("telegram_chat_id"),
        wallet_addresses=record.get("wallet_addresses", []),
        language=record.get("language", "zh"),
        wecom_enabled=bool(record.get("wecom_enabled")),
        wecom_webhook_url=record.get("wecom_webhook_url"),
        wecom_mentions=record.get("wecom_mentions", []),
    )
    uses_default = not record.get("telegram_bot_token") and bool(DEFAULT_TELEGRAM_BOT_TOKEN)
    return MonitorConfig(
        telegram_bot_token=None if uses_default else record.get("telegram_bot_token"),
        telegram_chat_id=record.get("telegram_chat_id"),
        wallet_addresses=record.get("wallet_addresses", []),
        language=record.get("language", "zh"),
        uses_default_bot=uses_default,
        default_bot_username=DEFAULT_TELEGRAM_BOT_USERNAME or None,
    )


@app.get("/api/binance_follow", response_model=BinanceFollowConfigResponse)
def fetch_binance_follow_config(
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> BinanceFollowConfigResponse:
    _ensure_monitor_access(current_user)
    record = get_binance_follow_config(current_user["id"])
    record["enabled"] = record.get("enabled", False)
    return _build_binance_response(record)


@app.post("/api/binance_follow", response_model=BinanceFollowConfigResponse)
def save_binance_follow_config(
    payload: BinanceFollowConfigRequest,
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> BinanceFollowConfigResponse:
    _ensure_monitor_access(current_user)
    existing = get_binance_follow_config(current_user["id"])

    api_key = (payload.api_key or "").strip()
    api_secret = (payload.api_secret or "").strip()

    if payload.reset_credentials:
        api_key = ""
        api_secret = ""

    if not api_key:
        api_key = existing.get("api_key") or ""
    if not api_secret:
        api_secret = existing.get("api_secret") or ""

    if payload.enabled and (not api_key or not api_secret):
        raise HTTPException(status_code=400, detail="Binance API Key 与 Secret 必须同时填写。")

    mode = payload.mode if payload.mode in {"fixed", "percentage"} else "fixed"
    amount = max(payload.amount, 0.0)
    stop_loss_amount = max(payload.stop_loss_amount, 0.0)
    max_position = max(payload.max_position, 0.0)
    min_order_size = max(payload.min_order_size, 0.0)

    enabled_flag = payload.enabled and bool(api_key and api_secret)

    record = upsert_binance_follow_config(
        current_user["id"],
        enabled=enabled_flag,
        wallet_address=(payload.wallet_address or "").lower(),
        mode=mode,
        amount=amount,
        stop_loss_amount=stop_loss_amount,
        max_position=max_position,
        min_order_size=min_order_size,
        api_key=api_key or None,
        api_secret=api_secret or None,
        baseline_balance=existing.get("baseline_balance") if enabled_flag else None,
        status=None,
        stop_reason=None,
    )
    configure_binance_follow(current_user["id"], record)
    return _build_binance_response(record)


@app.get("/api/wecom", response_model=WecomConfigResponse)
def fetch_wecom_config(
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> WecomConfigResponse:
    _ensure_monitor_access(current_user)
    record = get_wecom_config(current_user["id"])
    return _build_wecom_response(record)


@app.post("/api/wecom", response_model=WecomConfigResponse)
def save_wecom_config(
    payload: WecomConfigRequest,
    current_user: Dict[str, Any] = Depends(_require_current_user),
) -> WecomConfigResponse:
    _ensure_monitor_access(current_user)
    mentions = [item.strip() for item in payload.mentions if item.strip()]
    record = upsert_wecom_config(
        current_user["id"],
        enabled=payload.enabled and bool((payload.webhook_url or "").strip()),
        webhook_url=(payload.webhook_url or "").strip() or None,
        mentions=mentions,
    )
    full_config = get_user_config(current_user["id"])
    effective_token = full_config.get("telegram_bot_token") or DEFAULT_TELEGRAM_BOT_TOKEN or None
    configure_user_monitor(
        current_user["id"],
        telegram_bot_token=effective_token,
        telegram_chat_id=full_config.get("telegram_chat_id"),
        wallet_addresses=full_config.get("wallet_addresses", []),
        language=full_config.get("language", "zh"),
        wecom_enabled=record.get("enabled", False),
        wecom_webhook_url=record.get("webhook_url"),
        wecom_mentions=record.get("mentions", []),
    )
    return _build_wecom_response(record)


def _topic_to_address(topic: str) -> str:
    if topic.startswith("0x") and len(topic) == 66:
        return "0x" + topic[-40:]
    return topic


def _send_email(recipient: str, subject: str, body: str) -> None:
    if not EMAIL_ENABLED or not recipient:
        return
    clean_recipient = (recipient or "").replace("\u00a0", "").strip()
    clean_subject = (subject or "").replace("\u00a0", " ").strip()
    clean_from = (SMTP_FROM or SMTP_USERNAME or "").replace("\u00a0", "").strip()
    if not clean_from and SMTP_USERNAME:
        clean_from = SMTP_USERNAME.strip()
    clean_body = (body or "").replace("\u00a0", " ").strip()
    clean_username = (SMTP_USERNAME or "").replace("\u00a0", "").strip()
    clean_password = (SMTP_PASSWORD or "").replace("\u00a0", "").strip()
    message = EmailMessage()
    message["Subject"] = str(Header(clean_subject, "utf-8"))
    message["From"] = clean_from
    message["To"] = clean_recipient
    message.set_content(clean_body, charset="utf-8")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(clean_username, clean_password)
            server.send_message(message)
    except Exception as exc:  # pragma: no cover - email failures are non-critical
        logger.warning("Failed to send email to %s: %s", clean_recipient or recipient, exc)


def _get_tx_receipt(tx_hash: str) -> Dict[str, Any]:
    if BSC_RPC_URL:
        try:
            payload = {"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 1}
            response = requests.post(BSC_RPC_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if "error" in data and data["error"]:
                message = data["error"].get("message", "Unknown BSC RPC error")
                logger.error("BSC RPC error for tx %s: %s", tx_hash, message)
                raise HTTPException(status_code=400, detail=f"BSC RPC error: {message}")
            receipt = data.get("result")
            if receipt:
                return receipt
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Primary BSC RPC (%s) failed for tx %s: %s", BSC_RPC_URL, tx_hash, exc)
    if not BSCSCAN_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Unable to query transaction receipt. Configure BSC_RPC_URL or BSCSCAN_API_KEY.",
        )
    params = {
        "module": "proxy",
        "action": "eth_getTransactionReceipt",
        "txhash": tx_hash,
        "apikey": BSCSCAN_API_KEY,
    }
    response = requests.get(BSCSCAN_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    status_flag = payload.get("status")
    result = payload.get("result")
    if isinstance(result, str):
        message = payload.get("message") or "BscScan error"
        detail = f"{message}: {result}"
        logger.error("BscScan proxy error for tx %s: %s", tx_hash, detail)
        raise HTTPException(status_code=502, detail=f"BscScan error: {detail}")
    if status_flag == "0" and not result:
        message = payload.get("message") or "Unknown BscScan error"
        detail = f"{message}: {payload.get('result')}"
        logger.error("BscScan status=0 for tx %s: %s", tx_hash, detail)
        raise HTTPException(status_code=400, detail=detail)
    if not result:
        raise HTTPException(status_code=400, detail="Transaction not found or pending confirmation")
    return result


def _verify_payment_on_chain(tx_hash: str) -> Dict[str, Any]:
    result = _get_tx_receipt(tx_hash)
    if isinstance(result, str):
        raise HTTPException(status_code=502, detail=f"BSC RPC returned invalid result: {result}")
    if "status" in result and result.get("status") == "0x0":
        raise HTTPException(status_code=400, detail="Transaction failed on chain")

    contract = USDT_CONTRACT.lower()
    target = PAYMENT_TARGET_ADDRESS.lower()
    logs = result.get("logs", [])
    for entry in logs:
        if entry.get("address", "").lower() != contract:
            continue
        topics = entry.get("topics") or []
        if len(topics) < 3:
            continue
        to_address = _topic_to_address(topics[2]).lower()
        if to_address != target:
            continue
        amount_raw = int(entry.get("data", "0x0"), 16)
        if amount_raw < REQUIRED_AMOUNT_WEI:
            continue
        from_address = _topic_to_address(topics[1]).lower()
        block_number = int(result.get("blockNumber", "0x0"), 16)
        return {
            "from_address": from_address,
            "amount_raw": amount_raw,
            "block_number": block_number,
        }
    raise HTTPException(status_code=400, detail="No qualifying USDT transfer to the monitored address was found in the transaction")


def _check_subscription_reminders() -> None:
    now = _now()
    upcoming_threshold = now + timedelta(days=REMINDER_LEAD_DAYS)
    for user in list_users():
        subscription_end = _parse_iso(user.get("subscription_end"))
        if not subscription_end or subscription_end <= now or subscription_end > upcoming_threshold:
            continue
        last_reminder = _parse_iso(user.get("last_reminder_at"))
        if last_reminder and (now - last_reminder) < timedelta(days=1):
            continue
        if EMAIL_ENABLED:
            body = (
                "您的 Hyperliquid Monitor 订阅将于 "
                f"{subscription_end.isoformat()} 到期，请及时续费以继续使用监控配置功能。"
            )
            _send_email(user["email"], "Hyperliquid Monitor 订阅即将到期", body)
        update_user(user["id"], last_reminder_at=now.isoformat())


def _start_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started or REMINDER_LEAD_DAYS <= 0:
        return
    _scheduler_started = True
    try:
        schedule.clear("subscription-reminders")
    except Exception:  # pragma: no cover - scheduler exceptions are non-critical
        pass
    schedule.every().day.at(REMINDER_TIME).do(_check_subscription_reminders).tag("subscription-reminders")

    def runner() -> None:
        while True:
            schedule.run_pending()
            time.sleep(60)

    threading.Thread(target=runner, daemon=True).start()
