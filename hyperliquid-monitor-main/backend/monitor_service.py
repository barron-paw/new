import importlib.util
import logging
import os
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

try:
    import schedule  # type: ignore
except ImportError as exc:  # pragma: no cover - schedule is an optional dependency
    raise RuntimeError(
        "The 'schedule' package is required for monitoring. Install with `pip install schedule`."
    ) from exc

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MONITOR_POSITIONS_PATH = BASE_DIR / "monitor_positions.py"
STATE_STORE_PATH = BASE_DIR / "state_store.py"
STATE_ROOT = BASE_DIR / "state_store"
STATE_ROOT.mkdir(exist_ok=True)
DEFAULT_TELEGRAM_BOT_TOKEN = os.getenv("DEFAULT_TELEGRAM_BOT_TOKEN", "").strip()


class _SchedulerWrapper:
    """Provide an isolated scheduler per monitor thread."""

    def __init__(self) -> None:
        self._scheduler = schedule.Scheduler()

    def every(self, *args, **kwargs):
        return self._scheduler.every(*args, **kwargs)

    def run_pending(self) -> None:
        self._scheduler.run_pending()


@dataclass
class _UserConfig:
    user_id: int
    telegram_bot_token: str
    telegram_chat_id: str
    wallet_addresses: Tuple[str, ...]
    language: str = "zh"
    wecom_enabled: bool = False
    wecom_webhook_url: Optional[str] = None
    wecom_mentions: Tuple[str, ...] = ()


class UserMonitor:
    def __init__(self, config: _UserConfig) -> None:
        self.config = config
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._module = None
        self._state_module = None
        self._skip_snapshot_on_start = False

    def start(self) -> None:
        skip_snapshot = self._skip_snapshot_on_start
        self._skip_snapshot_on_start = False
        if self._thread and self._thread.is_alive():
            return
        if not self.config.wallet_addresses:
            logger.warning("User %s has no wallet addresses; monitor not started", self.config.user_id)
            return
        # 允许只使用企业微信推送，不需要 Telegram 凭证
        has_telegram = bool(self.config.telegram_bot_token and self.config.telegram_chat_id)
        has_wecom = bool(self.config.wecom_enabled and self.config.wecom_webhook_url)
        if not has_telegram and not has_wecom:
            logger.warning("User %s missing both Telegram and WeCom credentials; monitor not started", self.config.user_id)
            return
        if not has_telegram:
            logger.info("User %s starting monitor with WeCom only (no Telegram credentials)", self.config.user_id)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(skip_snapshot,), name=f"user-monitor-{self.config.user_id}", daemon=True)
        self._thread.start()
        logger.info("Started monitor thread for user %s", self.config.user_id)

    def stop(self) -> None:
        self._stop_event.set()
        module = self._module
        if module is not None:
            try:
                module._stop_event.set()  # type: ignore[attr-defined]
                module.stop_websocket_monitoring()
            except Exception as exc:  # pragma: no cover - defensive stop
                logger.debug("Error while stopping websocket monitoring for user %s: %s", self.config.user_id, exc)
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=30)
        self._thread = None
        self._module = None
        self._state_module = None
        logger.info("Stopped monitor for user %s", self.config.user_id)

    def update(
        self,
        *,
        telegram_bot_token: str,
        telegram_chat_id: str,
        wallet_addresses: Tuple[str, ...],
        language: str,
        wecom_enabled: bool,
        wecom_webhook_url: Optional[str],
        wecom_mentions: Tuple[str, ...],
    ) -> None:
        old_language = self.config.language
        normalized_language = (language or "zh").lower()
        if normalized_language not in {"zh", "en"}:
            normalized_language = "zh"
        restart_needed = (
            telegram_bot_token != self.config.telegram_bot_token
            or telegram_chat_id != self.config.telegram_chat_id
            or wallet_addresses != self.config.wallet_addresses
            or wecom_enabled != self.config.wecom_enabled
            or wecom_webhook_url != self.config.wecom_webhook_url
            or wecom_mentions != self.config.wecom_mentions
        )
        if restart_needed:
            logger.info("User %s: Configuration changed, restart needed. Changes: telegram_token=%s, telegram_chat_id=%s, wallets=%s, wecom_enabled=%s, wecom_webhook=%s, wecom_mentions=%s",
                       self.config.user_id,
                       telegram_bot_token != self.config.telegram_bot_token,
                       telegram_chat_id != self.config.telegram_chat_id,
                       wallet_addresses != self.config.wallet_addresses,
                       wecom_enabled != self.config.wecom_enabled,
                       wecom_webhook_url != self.config.wecom_webhook_url,
                       wecom_mentions != self.config.wecom_mentions)
        language_changed = normalized_language != old_language
        self.config = _UserConfig(
            user_id=self.config.user_id,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            wallet_addresses=wallet_addresses,
            language=normalized_language,
            wecom_enabled=wecom_enabled,
            wecom_webhook_url=wecom_webhook_url,
            wecom_mentions=wecom_mentions,
        )
        # 如果配置改变但不需要重启，或者启用了推送渠道，需要发送快照
        telegram_enabled = bool(self.config.telegram_chat_id)
        # 只要启用了推送渠道（Telegram 或企业微信），就发送快照
        # 这样可以确保用户保存配置后能收到快照消息
        should_send_snapshot_after_update = (
            not restart_needed and (
                language_changed 
                or self.config.wecom_enabled 
                or telegram_enabled
            ) and self.config.wallet_addresses  # 确保有钱包地址
        )
        
        logger.debug("User %s: update() called - restart_needed=%s, wecom_enabled=%s, telegram_enabled=%s, should_send_snapshot=%s",
                    self.config.user_id, restart_needed, self.config.wecom_enabled, telegram_enabled, should_send_snapshot_after_update)
        
        if self._module is not None:
            try:
                # 更新模块中的配置
                # Telegram 只有在 chat_id 存在时才启用
                setattr(self._module, "TELEGRAM_ENABLED", telegram_enabled)
                setattr(self._module, "TELEGRAM_BOT_TOKEN", self.config.telegram_bot_token)
                setattr(self._module, "TELEGRAM_CHAT_ID", self.config.telegram_chat_id)
                setattr(self._module, "CONFIGURED_ADDRESSES", self.config.wallet_addresses)
                setattr(self._module, "LANGUAGE", self.config.language)
                setattr(self._module, "WECOM_ENABLED", self.config.wecom_enabled)
                setattr(self._module, "WECOM_WEBHOOK_URL", self.config.wecom_webhook_url)
                setattr(self._module, "WECOM_MENTIONS", self.config.wecom_mentions)
                # 如果配置改变但不需要重启，强制发送快照
                if should_send_snapshot_after_update:
                    try:
                        logger.info("User %s: Configuration updated, sending snapshot (telegram=%s, wecom=%s, restart_needed=%s, wallets=%s)", 
                                   self.config.user_id,
                                   telegram_enabled,
                                   self.config.wecom_enabled,
                                   restart_needed,
                                   len(self.config.wallet_addresses))
                        self._module.send_wallet_snapshot(  # type: ignore[attr-defined]
                            self.config.wallet_addresses,
                            force=True,
                        )
                        logger.info("User %s: Snapshot send command executed", self.config.user_id)
                    except Exception as exc:
                        logger.error(
                            "Failed to send forced snapshot after config update for user %s: %s",
                            self.config.user_id,
                            exc,
                            exc_info=True,
                        )
            except Exception as exc:
                logger.error("Unable to update module config for user %s: %s", self.config.user_id, exc, exc_info=True)
        elif should_send_snapshot_after_update:
            # 如果模块不存在但需要发送快照，启动监控
            logger.info("User %s: Module not initialized, starting monitor to send snapshot", self.config.user_id)
            self._skip_snapshot_on_start = False
            self.start()
            
        if restart_needed:
            logger.info("User %s: Restarting monitor with snapshot", self.config.user_id)
            self._skip_snapshot_on_start = False
            # 重置快照初始化标志，确保重启后发送快照
            if self._module is not None:
                setattr(self._module, "_snapshot_initialized", False)
            self.stop()
            # 等待线程完全停止
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            self.start()
        elif not self._thread or not self._thread.is_alive():
            # 如果监控没有运行，启动它
            logger.info("User %s: Monitor not running, starting it", self.config.user_id)
            self._skip_snapshot_on_start = False
            self.start()

    # Internal helpers -----------------------------------------------------

    def _load_state_store_module(self, module_name: str):
        spec = importlib.util.spec_from_file_location(module_name, STATE_STORE_PATH)
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise RuntimeError("Failed to load state_store module")
        spec.loader.exec_module(module)
        return module

    def _load_monitor_module(self, module_name: str):
        spec = importlib.util.spec_from_file_location(module_name, MONITOR_POSITIONS_PATH)
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise RuntimeError("Failed to load monitor_positions module")
        spec.loader.exec_module(module)
        return module

    def _prepare_modules(self) -> None:
        user_id = self.config.user_id
        state_module_name = f"backend.state_store_user_{user_id}"
        monitor_module_name = f"backend.monitor_positions_user_{user_id}"

        original_state_store = sys.modules.get("backend.state_store")

        state_module = self._load_state_store_module(state_module_name)
        sys.modules["backend.state_store"] = state_module
        monitor_module = self._load_monitor_module(monitor_module_name)

        # Restore original shared module for the rest of the app
        if original_state_store is not None:
            sys.modules["backend.state_store"] = original_state_store
        else:
            sys.modules.pop("backend.state_store", None)

        self._state_module = state_module
        self._module = monitor_module

        # Configure state storage file per user
        state_file = STATE_ROOT / f"user_{user_id}_position_state.json"
        setattr(state_module, "_STATE_FILE", state_file)
        if hasattr(state_module, "_REDIS_URL"):
            state_module._REDIS_URL = None  # type: ignore[attr-defined]
            state_module._REDIS_CLIENT = None  # type: ignore[attr-defined]

    def _configure_module(self) -> None:
        module = self._module
        state_module = self._state_module
        assert module is not None and state_module is not None

        # 设置 Telegram 配置：只有在 chat_id 存在时才启用
        telegram_enabled = bool(self.config.telegram_chat_id)
        module.TELEGRAM_ENABLED = telegram_enabled  # type: ignore[attr-defined]
        module.TELEGRAM_BOT_TOKEN = self.config.telegram_bot_token  # type: ignore[attr-defined]
        module.TELEGRAM_CHAT_ID = self.config.telegram_chat_id  # type: ignore[attr-defined]
        module.CONFIGURED_ADDRESSES = self.config.wallet_addresses  # type: ignore[attr-defined]
        module._stop_event = threading.Event()  # type: ignore[attr-defined]
        module._snapshot_initialized = False  # type: ignore[attr-defined]  # 重置快照初始化标志，确保重启后发送快照
        module.schedule = _SchedulerWrapper()  # type: ignore[attr-defined]
        module.LANGUAGE = getattr(self.config, "language", "zh")  # type: ignore[attr-defined]
        module.USER_ID = self.config.user_id  # type: ignore[attr-defined]
        module.WECOM_ENABLED = getattr(self.config, "wecom_enabled", False)  # type: ignore[attr-defined]
        module.WECOM_WEBHOOK_URL = getattr(self.config, "wecom_webhook_url", None)  # type: ignore[attr-defined]
        module.WECOM_MENTIONS = getattr(self.config, "wecom_mentions", ())  # type: ignore[attr-defined]
        try:
            from .binance_follow_service import dispatch_trade_event

            def _event_processor(event: Dict[str, Any], user_id: int = self.config.user_id) -> None:
                dispatch_trade_event(user_id, event)

            module.EVENT_PROCESSOR = _event_processor  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("无法注入 Binance 事件处理器：%s", exc)

        # Refresh state store configuration to pick custom path/env
        try:
            state_module.refresh_state_store_configuration()
        except Exception as exc:
            logger.debug("State store refresh failed for user %s: %s", self.config.user_id, exc)

    def _start_monitoring(self, skip_snapshot: bool = False) -> None:
        module = self._module
        assert module is not None

        if not skip_snapshot:
            try:
                logger.info("User %s: Starting monitoring with snapshot, telegram=%s, wecom=%s", 
                           self.config.user_id, 
                           bool(self.config.telegram_bot_token and self.config.telegram_chat_id),
                           bool(self.config.wecom_enabled and self.config.wecom_webhook_url))
                # 强制发送快照（通过 send_wallet_snapshot 而不是 monitor_all_wallets）
                # 这样可以确保即使 _snapshot_initialized 为 True 也会发送
                if hasattr(module, "send_wallet_snapshot"):
                    module.send_wallet_snapshot(self.config.wallet_addresses, force=True)  # type: ignore[attr-defined]
                else:
                    module.monitor_all_wallets()  # type: ignore[attr-defined]
            except Exception as exc:
                logger.error("Initial snapshot failed for user %s: %s", self.config.user_id, exc, exc_info=True)

        websocket_thread = threading.Thread(
            target=module.start_websocket_monitoring,
            name=f"user-monitor-ws-{self.config.user_id}",
            daemon=True,
        )
        websocket_thread.start()

        # Schedule snapshot every 4 hours
        try:
            module.schedule.every(4).hours.do(  # type: ignore[attr-defined]
                lambda: module.send_wallet_snapshot(
                    self.config.wallet_addresses,
                    force=True,
                )
            )
        except Exception as exc:
            logger.error("Failed to schedule snapshot for user %s: %s", self.config.user_id, exc)

    def _scheduler_loop(self) -> None:
        module = self._module
        assert module is not None
        while not self._stop_event.is_set():
            try:
                module.schedule.run_pending()  # type: ignore[attr-defined]
            except Exception as exc:
                logger.error("Scheduler loop error for user %s: %s", self.config.user_id, exc)
            self._stop_event.wait(60)

    def _run(self, skip_snapshot: bool = False) -> None:
        start_time = datetime.utcnow()
        try:
            self._prepare_modules()
            self._configure_module()
            self._start_monitoring(skip_snapshot=skip_snapshot)
            self._scheduler_loop()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Monitor loop crashed for user %s: %s", self.config.user_id, exc)
        finally:
            self._stop_event.set()
            module = self._module
            if module is not None:
                try:
                    module._stop_event.set()  # type: ignore[attr-defined]
                    module.stop_websocket_monitoring()
                except Exception:
                    pass
            self._module = None
            self._state_module = None
            logger.info(
                "Monitor thread exited for user %s after %s seconds",
                self.config.user_id,
                (datetime.utcnow() - start_time).total_seconds(),
            )


class MonitorRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._monitors: Dict[int, UserMonitor] = {}

    @staticmethod
    def _normalize_addresses(addresses: Iterable[str]) -> Tuple[str, ...]:
        tokens = []
        seen = set()
        for entry in addresses:
            if not entry:
                continue
            for token in re.split(r"[\s,;]+", entry.strip()):
                token = token.strip().lower()
                if not token or token in seen:
                    continue
                tokens.append(token)
                seen.add(token)
        return tuple(tokens)

    def configure_user(
        self,
        user_id: int,
        *,
        telegram_bot_token: Optional[str],
        telegram_chat_id: Optional[str],
        wallet_addresses: Iterable[str],
        language: str,
        wecom_enabled: bool,
        wecom_webhook_url: Optional[str],
        wecom_mentions: Iterable[str],
    ) -> None:
        wallets_tuple = self._normalize_addresses(wallet_addresses)
        wallets_tuple = wallets_tuple[:2]
        token = (telegram_bot_token or "").strip()
        if not token and DEFAULT_TELEGRAM_BOT_TOKEN:
            token = DEFAULT_TELEGRAM_BOT_TOKEN
            logger.debug("Using default Telegram bot token for user %s", user_id)
        chat_id = (telegram_chat_id or "").strip()
        lang = (language or "zh").lower()
        if lang not in {"zh", "en"}:
            lang = "zh"
        webhook = (wecom_webhook_url or "").strip() or None
        mentions_tuple = tuple(item.strip() for item in wecom_mentions if item.strip())
        wecom_active = bool(wecom_enabled and webhook)

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
                    language=lang,
                    wecom_enabled=wecom_active,
                    wecom_webhook_url=webhook,
                    wecom_mentions=mentions_tuple,
                )
                return

            monitor = UserMonitor(
                _UserConfig(
                    user_id=user_id,
                    telegram_bot_token=token,
                    telegram_chat_id=chat_id,
                    wallet_addresses=wallets_tuple,
                    language=lang,
                    wecom_enabled=wecom_active,
                    wecom_webhook_url=webhook,
                    wecom_mentions=mentions_tuple,
                )
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
    language: str,
    wecom_enabled: bool,
    wecom_webhook_url: Optional[str],
    wecom_mentions: Iterable[str],
) -> None:
    registry.configure_user(
        user_id,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        wallet_addresses=wallet_addresses,
        language=language,
        wecom_enabled=wecom_enabled,
        wecom_webhook_url=wecom_webhook_url,
        wecom_mentions=wecom_mentions,
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
            language=config.get("language", "zh"),
            wecom_enabled=bool(config.get("wecom_enabled")),
            wecom_webhook_url=config.get("wecom_webhook_url"),
            wecom_mentions=config.get("wecom_mentions", []),
        )

