import importlib
import logging
import queue
import threading
import time
from dataclasses import dataclass, replace
import os
from typing import Any, Dict, Optional

try:  # Binance SDK 为可选依赖，未安装时提供兼容处理
    from binance.error import ClientError  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback when SDK missing
    class ClientError(Exception):  # type: ignore
        def __init__(
            self,
            message: str = "",
            *,
            status_code: Optional[int] = None,
            error_message: Optional[str] = None,
        ) -> None:
            super().__init__(message or error_message or "Binance client error")
            self.status_code = status_code
            self.error_message = error_message or message or ""

from .database import (
    get_binance_follow_config,
    list_users,
    update_binance_follow_status,
)

logger = logging.getLogger(__name__)

_BINANCE_API_URL = os.getenv("BINANCE_API_URL", "").strip()


def _float_or_zero(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value))
    except Exception:
        return 0.0


@dataclass
class FollowSettings:
    user_id: int
    enabled: bool
    wallet_address: str
    mode: str
    amount: float
    stop_loss_amount: float
    max_position: float
    min_order_size: float
    api_key: Optional[str]
    api_secret: Optional[str]
    baseline_balance: Optional[float]
    status: str
    stop_reason: Optional[str]


class BinanceFollower:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self._config: Optional[FollowSettings] = None
        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue(maxsize=1024)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._client: Optional[Any] = None
        self._last_stop_loss_check = 0.0

    # Public API -----------------------------------------------------------

    def apply_config(self, config: FollowSettings) -> None:
        previous = self._config
        self._config = config

        if not config.enabled:
            self.stop()
            return

        if not config.api_key or not config.api_secret:
            logger.warning("User %s 启用了跟单但未提供 Binance API 密钥，已忽略。", self.user_id)
            self.stop()
            update_binance_follow_status(
                self.user_id,
                enabled=False,
                status="disabled",
                stop_reason="缺少 Binance API Key/Secret",
            )
            return

        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=f"binance-follow-{self.user_id}",
                daemon=True,
            )
            self._thread.start()
            logger.info("启动用户 %s 的 Binance 跟单线程。", self.user_id)
        elif previous and previous.mode != config.mode:
            logger.info("用户 %s 跟单模式变更为 %s。", self.user_id, config.mode)

    def enqueue_event(self, event: Dict[str, Any]) -> None:
        if not self._config or not self._config.enabled:
            return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            logger.warning("用户 %s 的跟单事件队列已满，丢弃最新事件。", self.user_id)

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
            self._thread.join(timeout=5)
        self._thread = None
        self._client = None

    # Internal -------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=1.0)
            except queue.Empty:
                self._periodic_stop_loss_check()
                continue

            if event is None:
                break

            try:
                self._process_event(event)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("处理用户 %s Binance 跟单事件失败: %s", self.user_id, exc)

        logger.info("用户 %s 的 Binance 跟单线程结束。", self.user_id)

    def _periodic_stop_loss_check(self) -> None:
        now = time.time()
        if now - self._last_stop_loss_check < 10:
            return
        self._last_stop_loss_check = now
        self._check_stop_loss()

    def _process_event(self, event: Dict[str, Any]) -> None:
        config = self._config
        if not config or not config.enabled:
            return

        address = (event.get("address") or "").lower()
        if config.wallet_address and address != config.wallet_address.lower():
            return

        if self._check_stop_loss():
            return

        symbol = self._map_symbol(event.get("coin"))
        if not symbol:
            logger.warning("用户 %s 跟单事件缺少有效交易对，已跳过。", self.user_id)
            return

        trade_details = event.get("trade_details") or {}
        event_type = event.get("event_type")
        side = self._determine_side(event_type, trade_details, event)
        if not side:
            logger.debug("用户 %s 未能确定方向，事件 %s 已跳过。", self.user_id, event_type)
            return

        quantity = self._calculate_quantity(trade_details, event)
        if quantity <= 0:
            logger.debug("用户 %s 在事件 %s 计算得到的下单量为 0，已跳过。", self.user_id, event_type)
            return

        if config.min_order_size and quantity < config.min_order_size:
            logger.info(
                "用户 %s Binance 下单量 %.8f 低于最小阈值 %.8f，已跳过。",
                self.user_id,
                quantity,
                config.min_order_size,
            )
            return

        client = self._ensure_client()
        if client is None:
            return

        leverage = trade_details.get("leverage")
        if leverage:
            self._ensure_leverage(client, symbol, leverage)

        if not self._check_max_position(client, symbol, quantity, event_type):
            return

        reduce_only = event_type in {"reduced", "closed"}
        self._place_market_order(client, symbol, side, quantity, reduce_only)
        self._check_stop_loss()

    # Helpers --------------------------------------------------------------

    def _ensure_client(self) -> Optional[Any]:
        if self._client is not None:
            return self._client
        config = self._config
        if not config:
            return None
        try:
            module = importlib.import_module("binance.um_futures")
        except ModuleNotFoundError:
            logger.error(
                "未找到 binance-connector，请执行 `pip install binance-connector` 后重启服务。"
            )
            update_binance_follow_status(
                self.user_id,
                enabled=False,
                status="disabled",
                stop_reason="缺少 binance-connector 包",
            )
            self._config = replace(config, enabled=False)
            return None

        UMFutures = getattr(module, "UMFutures", None)
        if UMFutures is None:
            logger.error("binance-connector 缺少 UMFutures 类，请检查依赖版本。")
            update_binance_follow_status(
                self.user_id,
                enabled=False,
                status="disabled",
                stop_reason="binance-connector 版本不兼容",
            )
            self._config = replace(config, enabled=False)
            return None

        try:
            self._client = UMFutures(
                key=config.api_key,
                secret=config.api_secret,
                base_url=_BINANCE_API_URL or None,
            )
            if config.baseline_balance is None:
                balance = self._fetch_total_wallet_balance(self._client)
                if balance is not None:
                    config = replace(config, baseline_balance=balance)
                    self._config = config
                    update_binance_follow_status(
                        self.user_id,
                        baseline_balance=balance,
                        status="active",
                        enabled=True,
                        stop_reason=None,
                    )
        except Exception as exc:  # pragma: no cover - network / credential
            logger.error("初始化用户 %s 的 Binance 客户端失败: %s", self.user_id, exc)
            update_binance_follow_status(
                self.user_id,
                enabled=False,
                status="disabled",
                stop_reason="Binance API 初始化失败",
            )
            self._config = replace(config, enabled=False)
            return None
        return self._client

    def _fetch_total_wallet_balance(self, client: Any) -> Optional[float]:
        try:
            account = client.account()
            balance = account.get("totalWalletBalance")
            return _float_or_zero(balance)
        except ClientError as exc:  # pragma: no cover - external API
            logger.error("获取用户 %s Binance 账户余额失败: %s", self.user_id, exc.error_message)
        except Exception as exc:
            logger.error("获取用户 %s Binance 账户余额发生异常: %s", self.user_id, exc)
        return None

    def _check_stop_loss(self) -> bool:
        config = self._config
        client = self._ensure_client()
        if not config or not config.enabled or not client:
            return False
        if not config.stop_loss_amount or config.stop_loss_amount <= 0:
            return False
        if config.baseline_balance is None:
            return False
        current_balance = self._fetch_total_wallet_balance(client)
        if current_balance is None:
            return False
        loss = config.baseline_balance - current_balance
        if loss >= config.stop_loss_amount:
            logger.warning(
                "用户 %s Binance 账户亏损 %.2f 超过设定阈值 %.2f，自动停止跟单。",
                self.user_id,
                loss,
                config.stop_loss_amount,
            )
            update_binance_follow_status(
                self.user_id,
                enabled=False,
                status="stopped_by_loss",
                stop_reason=f"亏损 {loss:.2f} ≥ 阈值 {config.stop_loss_amount:.2f}",
            )
            self._config = replace(config, enabled=False, stop_reason="stop_loss_triggered")
            self.stop()
            return True
        return False

    def _ensure_leverage(self, client: Any, symbol: str, leverage: Any) -> None:
        try:
            target = int(round(float(leverage)))
            if target < 1 or target > 125:
                return
        except Exception:
            return
        try:
            client.change_leverage(symbol=symbol, leverage=target)
        except ClientError as exc:  # pragma: no cover - external API
            if exc.status_code != 400:
                logger.warning("调整用户 %s %s 杠杆失败: %s", self.user_id, symbol, exc.error_message)
        except Exception as exc:
            logger.warning("调整用户 %s %s 杠杆异常: %s", self.user_id, symbol, exc)

    def _calculate_quantity(self, trade_details: Dict[str, Any], event: Dict[str, Any]) -> float:
        config = self._config
        if not config:
            return 0.0
        mode = config.mode
        size = _float_or_zero(trade_details.get("size"))
        if size <= 0:
            previous_position = event.get("previous_position") or {}
            current_position = event.get("current_position") or {}
            prev_size = abs(_float_or_zero(previous_position.get("szi")))
            curr_size = abs(_float_or_zero(current_position.get("szi")))
            diff = abs(prev_size - curr_size)
            size = diff if diff > 0 else curr_size
        if size <= 0:
            size = abs(_float_or_zero(trade_details.get("position_size")))
        if mode == "percentage":
            percent = config.amount
            return max(0.0, size * percent / 100.0)
        return max(0.0, config.amount)

    def _determine_side(self, event_type: str, trade_details: Dict[str, Any], event: Dict[str, Any]) -> Optional[str]:
        side_hint = (trade_details.get("side") or "").upper()
        if side_hint == "B":
            return "BUY"
        if side_hint == "A":
            return "SELL"

        if event_type == "opened":
            current_position = event.get("current_position") or {}
            size = _float_or_zero(current_position.get("szi"))
            return "BUY" if size >= 0 else "SELL"

        previous_position = event.get("previous_position") or {}
        size = _float_or_zero(previous_position.get("szi"))
        if event_type in {"reduced", "closed"}:
            return "SELL" if size > 0 else "BUY"
        return None

    def _check_max_position(self, client: Any, symbol: str, quantity: float, event_type: str) -> bool:
        config = self._config
        if not config or not config.max_position or config.max_position <= 0:
            return True
        if event_type in {"reduced", "closed"}:
            return True
        try:
            positions = client.position_risk(symbol=symbol)
            if isinstance(positions, list) and positions:
                position_amt = abs(_float_or_zero(positions[0].get("positionAmt")))
                if position_amt + quantity > config.max_position + 1e-8:
                    logger.info(
                        "用户 %s 当前仓位 %.4f，加上计划下单 %.4f 将超过最大仓位 %.4f，已跳过。",
                        self.user_id,
                        position_amt,
                        quantity,
                        config.max_position,
                    )
                    return False
        except ClientError as exc:  # pragma: no cover - external API
            logger.warning("查询用户 %s Binance 仓位失败: %s", self.user_id, exc.error_message)
        except Exception as exc:
            logger.warning("查询用户 %s Binance 仓位异常: %s", self.user_id, exc)
        return True

    def _place_market_order(
        self,
        client: Any,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool,
    ) -> None:
        qty_formatted = f"{quantity:.8f}".rstrip("0").rstrip(".")
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": qty_formatted,
            "reduceOnly": "true" if reduce_only else "false",
        }
        try:
            client.new_order(**params)
            logger.info(
                "用户 %s 已在 Binance 以 %s 方向下单 %s %s (reduceOnly=%s)。",
                self.user_id,
                side,
                qty_formatted,
                symbol,
                reduce_only,
            )
        except ClientError as exc:  # pragma: no cover - external API
            logger.warning("用户 %s Binance 下单失败: %s", self.user_id, exc.error_message)
        except Exception as exc:
            logger.warning("用户 %s Binance 下单异常: %s", self.user_id, exc)

    def _map_symbol(self, coin: Any) -> Optional[str]:
        if not coin:
            return None
        coin_str = str(coin).upper().replace("PERP", "").strip()
        if not coin_str:
            return None
        if coin_str.endswith("USDT"):
            return coin_str
        return f"{coin_str}USDT"


class BinanceFollowRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._followers: Dict[int, BinanceFollower] = {}

    def configure_user(self, settings: FollowSettings) -> None:
        with self._lock:
            follower = self._followers.get(settings.user_id)
            if follower is None:
                follower = BinanceFollower(settings.user_id)
                self._followers[settings.user_id] = follower
            follower.apply_config(settings)
            if not settings.enabled:
                follower.stop()
                self._followers.pop(settings.user_id, None)

    def handle_event(self, user_id: int, event: Dict[str, Any]) -> None:
        with self._lock:
            follower = self._followers.get(user_id)
        if follower:
            follower.enqueue_event(event)

    def shutdown(self) -> None:
        with self._lock:
            followers = list(self._followers.values())
            self._followers.clear()
        for follower in followers:
            follower.stop()


_registry = BinanceFollowRegistry()


def _settings_from_dict(user_id: int, payload: Dict[str, Any]) -> FollowSettings:
    mode = (payload.get("mode") or "fixed").lower()
    if mode not in {"fixed", "percentage"}:
        mode = "fixed"
    return FollowSettings(
        user_id=user_id,
        enabled=bool(payload.get("enabled")),
        wallet_address=(payload.get("wallet_address") or "").lower(),
        mode=mode,
        amount=float(payload.get("amount") or 0.0),
        stop_loss_amount=float(payload.get("stop_loss_amount") or 0.0),
        max_position=float(payload.get("max_position") or 0.0),
        min_order_size=float(payload.get("min_order_size") or 0.0),
        api_key=payload.get("api_key"),
        api_secret=payload.get("api_secret"),
        baseline_balance=payload.get("baseline_balance"),
        status=payload.get("status") or "disabled",
        stop_reason=payload.get("stop_reason"),
    )


def configure_user_follow(user_id: int, config: Optional[Dict[str, Any]] = None) -> None:
    payload = config or get_binance_follow_config(user_id)
    settings = _settings_from_dict(user_id, payload)
    _registry.configure_user(settings)


def initialise_followers_from_db() -> None:
    for user in list_users():
        user_id = user.get("id")
        if not user_id:
            continue
        configure_user_follow(user_id)


def dispatch_trade_event(user_id: int, event: Dict[str, Any]) -> None:
    _registry.handle_event(user_id, event)


def shutdown_followers() -> None:
    _registry.shutdown()