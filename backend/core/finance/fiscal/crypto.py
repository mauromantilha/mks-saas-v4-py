from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class TokenCryptoError(RuntimeError):
    """Raised when token encryption/decryption fails."""


_fernet: Fernet | None = None


def _get_fernet_key() -> bytes:
    # Recommended: set a stable Fernet key (base64 urlsafe 32 bytes) via Secret Manager.
    configured = (getattr(settings, "FISCAL_TOKEN_ENCRYPTION_KEY", "") or "").strip()
    if configured:
        return configured.encode("utf-8")

    # Fallback (local/dev): derive from SECRET_KEY. Do not rely on this in production,
    # because rotating SECRET_KEY will make previously stored tokens undecryptable.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_fernet_key())
    return _fernet


def encrypt_token(token: str) -> str:
    if not token:
        return ""
    value = _get_fernet().encrypt(token.encode("utf-8"))
    return value.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    try:
        value = _get_fernet().decrypt(encrypted_token.encode("utf-8"))
        return value.decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - depends on stored data
        raise TokenCryptoError("Invalid encrypted token.") from exc

