import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_FERNET_INSTANCE: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE

    secret = os.getenv("BINANCE_ENCRYPTION_KEY", "").strip()
    if not secret:
        raise RuntimeError(
            "BINANCE_ENCRYPTION_KEY 环境变量未配置，无法安全存储 Binance API 密钥。"
        )

    try:
        if len(secret) == 44:
            key_bytes = secret.encode("utf-8")
            base64.urlsafe_b64decode(key_bytes)
        else:
            digest = hashlib.sha256(secret.encode("utf-8")).digest()
            key_bytes = base64.urlsafe_b64encode(digest)
        fernet = Fernet(key_bytes)
    except Exception as exc:  # pragma: no cover - defensive branch
        raise RuntimeError("BINANCE_ENCRYPTION_KEY 格式错误，无法初始化加密器。") from exc

    _FERNET_INSTANCE = fernet
    return fernet


def encrypt_value(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    fernet = _get_fernet()
    token = fernet.encrypt(raw.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(token: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    token = token.strip()
    if not token:
        return None
    fernet = _get_fernet()
    try:
        value = fernet.decrypt(token.encode("utf-8"))
        return value.decode("utf-8")
    except InvalidToken:
        logger.error("解密 Binance 密钥失败：密文无效或密钥已变更。")
        return None

