import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
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
            }
        raw_wallets = row["wallet_addresses"] or "[]"
        try:
            wallets = json.loads(raw_wallets)
            if not isinstance(wallets, list):
                wallets = []
        except json.JSONDecodeError:
            wallets = [addr.strip() for addr in raw_wallets.split(",") if addr.strip()]
        return {
            "telegram_bot_token": row["telegram_bot_token"],
            "telegram_chat_id": row["telegram_chat_id"],
            "wallet_addresses": wallets,
            "updated_at": row["updated_at"],
        }


def upsert_user_config(
    user_id: int,
    telegram_bot_token: Optional[str],
    telegram_chat_id: Optional[str],
    wallet_addresses: List[str],
) -> Dict[str, Any]:
    payload = json.dumps(wallet_addresses)
    updated_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_configs (user_id, telegram_bot_token, telegram_chat_id, wallet_addresses, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                telegram_bot_token = excluded.telegram_bot_token,
                telegram_chat_id = excluded.telegram_chat_id,
                wallet_addresses = excluded.wallet_addresses,
                updated_at = excluded.updated_at
            """,
            (user_id, telegram_bot_token, telegram_chat_id, payload, updated_at),
        )
        conn.commit()
    return get_user_config(user_id)


def update_user(user_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields.keys())
    values = list(fields.values())
    values.append(user_id)
    with get_db() as conn:
        conn.execute(f"UPDATE users SET {columns} WHERE id = ?", values)
        conn.commit()


# Initialise database when module is imported
init_db()
