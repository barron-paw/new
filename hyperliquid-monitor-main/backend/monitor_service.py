import logging
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Iterable, Optional, Tuple

import requests
from hyperliquid_monitor.monitor import HyperliquidMonitor
from hyperliquid_monitor.types import Trade

logger = logging.getLogger(__name__)

RECENT_TRADES_LIMIT = 1000


def _format_trade_message(trade: Trade) -> str:
    side = trade.side
    if side == "SELL":
        side = "BUY"
    elif side == "BUY":
        side = "SELL"

    trade_time = trade.timestamp
    if trade_time.tzinfo is None:
        trade_time = trade_time.replace(tzinfo=timezone.utc)
    trade_time_utc8 = trade_time.astimezone(timezone(timedelta(hours=8)))
    trade_time_str = trade_time_utc8.strftime("%Y-%m-%d %H:%M:%S UTC+8")

    return (
        "New trade detected:\n"
        f"Address: {trade.address}\n"
        f"Coin: {trade.coin}\n"
        f"Side: {side}\n"
        f"Size: {trade.size}\n"
        f"Price: {trade.price}\n"
        f"Type: {trade.trade_type}\n"
        f"Tx Hash: {trade.tx_hash}\n"
        f"Time: {trade_time_str}"
    )


def _send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Failed to send Telegram message: %s", exc, exc_info=True)
        return False


class UserMonitor:
    def __init__(
        self,
        *,
        user_id: int,
        telegram_bot_token: str,
        telegram_chat_id: str,
        wallet_addresses: Tuple[str, ...],
    ) -> None:
        self.user_id = user_id
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.wallet_addresses = wallet_addresses

        self._monitor: Optional[HyperliquidMonitor] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._recent_keys: deque = deque(maxlen=RECENT_TRADES_LIMIT)
        self._recent_set = set()
        self._startup_timestamp = datetime.now(timezone.utc)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not self.wallet_addresses:
            logger.warning("User %s has no wallet addresses; monitor not started", self.user_id)
            return
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("User %s missing Telegram credentials; monitor not started", self.user_id)
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=f"user-monitor-{self.user_id}", daemon=True)
        self._thread.start()
        logger.info("Started monitor thread for user %s", self.user_id)

    def stop(self) -> None:
        self._stop_event.set()
        if self._monitor is not None:
            try:
                self._monitor.stop()
            except Exception as exc:  # pragma: no cover
                logger.error("Error stopping monitor for user %s: %s", self.user_id, exc)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=15)
        self._monitor = None
        self._thread = None
        self._recent_keys.clear()
        self._recent_set.clear()
        logger.info("Stopped monitor for user %s", self.user_id)

    def update(
        self,
        *,
        telegram_bot_token: str,
        telegram_chat_id: str,
        wallet_addresses: Tuple[str, ...],
    ) -> None:
        restart_needed = (
            telegram_bot_token != self.telegram_bot_token
            or telegram_chat_id != self.telegram_chat_id
            or wallet_addresses != self.wallet_addresses
        )
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.wallet_addresses = wallet_addresses
        if restart_needed:
            self.stop()
            self.start()

    def _remember_trade(self, trade_key) -> bool:
        if trade_key in self._recent_set:
            return False
        if len(self._recent_keys) >= RECENT_TRADES_LIMIT:
            oldest = self._recent_keys.popleft()
            self._recent_set.discard(oldest)
        self._recent_keys.append(trade_key)
        self._recent_set.add(trade_key)
        return True

    def _handle_trade(self, trade: Trade) -> None:
        trade_time = trade.timestamp
        if trade_time.tzinfo is None:
            trade_time = trade_time.replace(tzinfo=timezone.utc)
        if trade_time < self._startup_timestamp:
            return

        trade_key = (trade.tx_hash, trade.size, trade.price)
        if not self._remember_trade(trade_key):
            return

        message = _format_trade_message(trade)
        if not _send_telegram_message(self.telegram_bot_token, self.telegram_chat_id, message):
            logger.warning("Telegram notification failed for user %s trade %s", self.user_id, trade.tx_hash)

    def _run(self) -> None:
        self._startup_timestamp = datetime.now(timezone.utc)
        try:
            monitor = HyperliquidMonitor(
                addresses=self.wallet_addresses,
                callback=self._handle_trade,
                db_path=None,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to initialise monitor for user %s: %s", self.user_id, exc)
            return

        self._monitor = monitor
        try:
            try:
                monitor.start(handle_signals=False)  # type: ignore[call-arg]
            except TypeError:
                monitor.start()
        except Exception as exc:  # pragma: no cover
            logger.error("Monitor loop crashed for user %s: %s", self.user_id, exc)
        finally:
            try:
                monitor.stop()
            except Exception:
                pass
            self._monitor = None
            logger.info("Monitor thread exited for user %s", self.user_id)


class MonitorRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._monitors: Dict[int, UserMonitor] = {}

    def configure_user(
        self,
        user_id: int,
        *,
        telegram_bot_token: Optional[str],
        telegram_chat_id: Optional[str],
        wallet_addresses: Iterable[str],
    ) -> None:
        wallets_tuple = tuple(addr.strip() for addr in wallet_addresses if addr.strip())
        token = (telegram_bot_token or "").strip()
        chat_id = (telegram_chat_id or "").strip()

        with self._lock:
            existing = self._monitors.get(user_id)
            if not token or not chat_id or not wallets_tuple:
                if existing:
                    existing.stop()
                    self._monitors.pop(user_id, None)
                    logger.info("Disabled monitor for user %s (incomplete configuration)", user_id)
                return

            if existing:
                existing.update(
                    telegram_bot_token=token,
                    telegram_chat_id=chat_id,
                    wallet_addresses=wallets_tuple,
                )
                return

            monitor = UserMonitor(
                user_id=user_id,
                telegram_bot_token=token,
                telegram_chat_id=chat_id,
                wallet_addresses=wallets_tuple,
            )
            self._monitors[user_id] = monitor
            monitor.start()

    def stop_all(self) -> None:
        with self._lock:
            for monitor in list(self._monitors.values()):
                monitor.stop()
            self._monitors.clear()


registry = MonitorRegistry()


def configure_user_monitor(
    user_id: int,
    *,
    telegram_bot_token: Optional[str],
    telegram_chat_id: Optional[str],
    wallet_addresses: Iterable[str],
) -> None:
    registry.configure_user(
        user_id,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        wallet_addresses=wallet_addresses,
    )


def shutdown_monitors() -> None:
    registry.stop_all()


def initialise_monitors_from_db() -> None:
    try:
        from .database import get_user_config, list_users
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to load user configurations: %s", exc)
        return

    for user in list_users():
        config = get_user_config(user["id"])
        configure_user_monitor(
            user["id"],
            telegram_bot_token=config.get("telegram_bot_token"),
            telegram_chat_id=config.get("telegram_chat_id"),
            wallet_addresses=config.get("wallet_addresses", []),
        )

