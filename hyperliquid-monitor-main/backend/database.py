import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .crypto_utils import decrypt_value, encrypt_value

DB_PATH = Path(__file__).resolve().parent / "data.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                trial_end TEXT NOT NULL,
                subscription_end TEXT,
                last_payment_hash TEXT,
                last_reminder_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_configs (
                user_id INTEGER PRIMARY KEY,
                telegram_bot_token TEXT,
                telegram_chat_id TEXT,
                wallet_addresses TEXT,
                updated_at TEXT,
                language TEXT DEFAULT 'zh',
                binance_follow_enabled INTEGER DEFAULT 0,
                binance_wallet_address TEXT,
                binance_mode TEXT,
                binance_amount REAL,
                binance_stop_loss_amount REAL,
                binance_max_position REAL,
                binance_min_order_size REAL,
                binance_api_key TEXT,
                binance_api_secret TEXT,
                binance_baseline_balance REAL,
                binance_follow_status TEXT DEFAULT 'disabled',
                binance_follow_stop_reason TEXT,
                wecom_enabled INTEGER DEFAULT 0,
                wecom_webhook_url TEXT,
                wecom_mentions TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verifications (
                email TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        # Ensure newer columns exist for legacy databases
        cursor = conn.execute("PRAGMA table_info(user_configs)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            "language": "TEXT DEFAULT 'zh'",
            "binance_follow_enabled": "INTEGER DEFAULT 0",
            "binance_wallet_address": "TEXT",
            "binance_mode": "TEXT",
            "binance_amount": "REAL",
            "binance_stop_loss_amount": "REAL",
            "binance_max_position": "REAL",
            "binance_min_order_size": "REAL",
            "binance_api_key": "TEXT",
            "binance_api_secret": "TEXT",
            "binance_baseline_balance": "REAL",
            "binance_follow_status": "TEXT DEFAULT 'disabled'",
            "binance_follow_stop_reason": "TEXT",
            "wecom_enabled": "INTEGER DEFAULT 0",
            "wecom_webhook_url": "TEXT",
            "wecom_mentions": "TEXT",
        }
        for column, ddl in required_columns.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE user_configs ADD COLUMN {column} {ddl}")
        conn.commit()


@contextmanager
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_user(email: str, password_hash: str, trial_days: int) -> Dict[str, Any]:
    email = email.lower()
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=trial_days)
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, created_at, trial_end)
            VALUES (?, ?, ?, ?)
            """,
            (email, password_hash, now.isoformat(), trial_end.isoformat()),
        )
        conn.commit()
        user_id = cursor.lastrowid
    return get_user_by_id(user_id)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_payment_hash(tx_hash: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE last_payment_hash = ?", (tx_hash.lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_user_config(user_id: int) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM user_configs WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {
                "telegram_bot_token": None,
                "telegram_chat_id": None,
                "wallet_addresses": [],
                "updated_at": None,
                "language": "zh",
            }
        raw_wallets = row["wallet_addresses"] or "[]"
        try:
            wallets = json.loads(raw_wallets)
            if not isinstance(wallets, list):
                wallets = []
        except json.JSONDecodeError:
            wallets = [addr.strip() for addr in raw_wallets.split(",") if addr.strip()]
        language = "zh"
        if hasattr(row, "keys") and "language" in row.keys():
            value = row["language"] or "zh"
            language = value.lower() if isinstance(value, str) else "zh"
            if language not in {"zh", "en"}:
                language = "zh"
        return {
            "telegram_bot_token": row["telegram_bot_token"],
            "telegram_chat_id": row["telegram_chat_id"],
            "wallet_addresses": wallets,
            "updated_at": row["updated_at"],
            "language": language,
            "wecom_enabled": bool(row.get("wecom_enabled", 0)),
            "wecom_webhook_url": row.get("wecom_webhook_url"),
            "wecom_mentions": (row.get("wecom_mentions") or "").split(",") if row.get("wecom_mentions") else [],
        }


def upsert_user_config(
    user_id: int,
    telegram_bot_token: Optional[str],
    telegram_chat_id: Optional[str],
    wallet_addresses: List[str],
    language: str,
) -> Dict[str, Any]:
    payload = json.dumps(wallet_addresses)
    updated_at = datetime.now(timezone.utc).isoformat()
    language_value = (language or "zh").lower()
    if language_value not in {"zh", "en"}:
        language_value = "zh"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_configs (user_id, telegram_bot_token, telegram_chat_id, wallet_addresses, updated_at, language)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                telegram_bot_token = excluded.telegram_bot_token,
                telegram_chat_id = excluded.telegram_chat_id,
                wallet_addresses = excluded.wallet_addresses,
                updated_at = excluded.updated_at,
                language = excluded.language
            """,
            (user_id, telegram_bot_token, telegram_chat_id, payload, updated_at, language_value),
        )
        conn.commit()
    return get_user_config(user_id)


def get_wecom_config(user_id: int) -> Dict[str, Any]:
    record = get_user_config(user_id)
    mentions = record.get("wecom_mentions") or []
    if isinstance(mentions, str):
        mentions = [item for item in mentions.split(",") if item]
    return {
        "enabled": bool(record.get("wecom_enabled")),
        "webhook_url": record.get("wecom_webhook_url"),
        "mentions": mentions,
    }


def upsert_wecom_config(
    user_id: int,
    *,
    enabled: bool,
    webhook_url: Optional[str],
    mentions: Optional[List[str]],
) -> Dict[str, Any]:
    mentions_value = ",".join([item.strip() for item in mentions or [] if item.strip()])
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_configs (
                user_id,
                wecom_enabled,
                wecom_webhook_url,
                wecom_mentions
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                wecom_enabled = excluded.wecom_enabled,
                wecom_webhook_url = excluded.wecom_webhook_url,
                wecom_mentions = excluded.wecom_mentions
            """,
            (user_id, 1 if enabled else 0, (webhook_url or "").strip() or None, mentions_value or None),
        )
        conn.commit()
    return get_wecom_config(user_id)


def get_binance_follow_config(user_id: int) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT
                binance_follow_enabled,
                binance_wallet_address,
                binance_mode,
                binance_amount,
                binance_stop_loss_amount,
                binance_max_position,
                binance_min_order_size,
                binance_api_key,
                binance_api_secret,
                binance_baseline_balance,
                binance_follow_status,
                binance_follow_stop_reason
            FROM user_configs
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
    if not row:
        return {
            "enabled": False,
            "wallet_address": "",
            "mode": "fixed",
            "amount": 0.0,
            "stop_loss_amount": 0.0,
            "max_position": 0.0,
            "min_order_size": 0.0,
            "api_key": None,
            "api_secret": None,
            "baseline_balance": None,
            "status": "disabled",
            "stop_reason": None,
        }
    return {
        "enabled": bool(row["binance_follow_enabled"]),
        "wallet_address": row["binance_wallet_address"] or "",
        "mode": (row["binance_mode"] or "fixed").lower(),
        "amount": row["binance_amount"] or 0.0,
        "stop_loss_amount": row["binance_stop_loss_amount"] or 0.0,
        "max_position": row["binance_max_position"] or 0.0,
        "min_order_size": row["binance_min_order_size"] or 0.0,
        "api_key": decrypt_value(row["binance_api_key"]),
        "api_secret": decrypt_value(row["binance_api_secret"]),
        "baseline_balance": row["binance_baseline_balance"],
        "status": row["binance_follow_status"] or "disabled",
        "stop_reason": row["binance_follow_stop_reason"],
    }


def upsert_binance_follow_config(
    user_id: int,
    *,
    enabled: bool,
    wallet_address: Optional[str],
    mode: str,
    amount: float,
    stop_loss_amount: float,
    max_position: float,
    min_order_size: float,
    api_key: Optional[str],
    api_secret: Optional[str],
    baseline_balance: Optional[float],
    status: Optional[str] = None,
    stop_reason: Optional[str] = None,
) -> Dict[str, Any]:
    wallet_address = (wallet_address or "").strip().lower()
    normalized_mode = mode.lower() if mode in {"fixed", "percentage"} else "fixed"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_configs (
                user_id,
                binance_follow_enabled,
                binance_wallet_address,
                binance_mode,
                binance_amount,
                binance_stop_loss_amount,
                binance_max_position,
                binance_min_order_size,
                binance_api_key,
                binance_api_secret,
                binance_baseline_balance,
                binance_follow_status,
                binance_follow_stop_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                binance_follow_enabled = excluded.binance_follow_enabled,
                binance_wallet_address = excluded.binance_wallet_address,
                binance_mode = excluded.binance_mode,
                binance_amount = excluded.binance_amount,
                binance_stop_loss_amount = excluded.binance_stop_loss_amount,
                binance_max_position = excluded.binance_max_position,
                binance_min_order_size = excluded.binance_min_order_size,
                binance_api_key = excluded.binance_api_key,
                binance_api_secret = excluded.binance_api_secret,
                binance_baseline_balance = excluded.binance_baseline_balance,
                binance_follow_status = excluded.binance_follow_status,
                binance_follow_stop_reason = excluded.binance_follow_stop_reason
            """,
            (
                user_id,
                1 if enabled else 0,
                wallet_address or None,
                normalized_mode,
                amount,
                stop_loss_amount,
                max_position,
                min_order_size,
                encrypt_value(api_key),
                encrypt_value(api_secret),
                baseline_balance,
                status or ("active" if enabled else "disabled"),
                stop_reason,
            ),
        )
        conn.commit()
    return get_binance_follow_config(user_id)


def update_binance_follow_status(
    user_id: int,
    *,
    enabled: Optional[bool] = None,
    status: Optional[str] = None,
    stop_reason: Optional[str] = None,
    baseline_balance: Optional[float] = None,
) -> None:
    assignments = []
    values: List[Any] = []
    if enabled is not None:
        assignments.append("binance_follow_enabled = ?")
        values.append(1 if enabled else 0)
    if status is not None:
        assignments.append("binance_follow_status = ?")
        values.append(status)
    if stop_reason is not None:
        assignments.append("binance_follow_stop_reason = ?")
        values.append(stop_reason)
    if baseline_balance is not None:
        assignments.append("binance_baseline_balance = ?")
        values.append(baseline_balance)
    if not assignments:
        return
    values.append(user_id)
    with get_db() as conn:
        conn.execute(
            f"UPDATE user_configs SET {', '.join(assignments)} WHERE user_id = ?",
            values,
        )
        conn.commit()


def update_user(user_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields.keys())
    values = list(fields.values())
    values.append(user_id)
    with get_db() as conn:
        conn.execute(f"UPDATE users SET {columns} WHERE id = ?", values)
        conn.commit()


def upsert_email_verification(email: str, code: str, expires_at: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO email_verifications (email, code, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                code = excluded.code,
                expires_at = excluded.expires_at
            """,
            (email.lower(), code, expires_at),
        )
        conn.commit()


def consume_email_verification(email: str, code: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT code, expires_at FROM email_verifications WHERE email = ?",
            (email.lower(),),
        )
        row = cursor.fetchone()
        if not row:
            return False
        stored_code = row[0]
        expires_at = row[1]
        if stored_code != code:
            return False
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        conn.execute("DELETE FROM email_verifications WHERE email = ?", (email.lower(),))
        conn.commit()
        return expiry >= datetime.utcnow()


# Initialise database when module is imported
init_db()
