"""Cifrado de campos personales en reposo e índices ciegos (V5, ampliado con rotación de claves).

- Fernet (AES-128-CBC + HMAC-SHA256). FIELD_ENCRYPTION_KEY admite varias claves separadas por coma:
  la primera cifra y todas descifran (MultiFernet), lo que permite rotar sin perder datos.
- blind_index: HMAC-SHA256 determinista para buscar por correo sin guardarlo en claro.
"""
import hashlib
import hmac
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings


@lru_cache
def _fernet() -> MultiFernet:
    raw = get_settings().field_encryption_key.get_secret_value()
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def _index_key() -> bytes:
    s = get_settings()
    key = s.blind_index_key or s.secret_key
    return key.get_secret_value().encode()


def blind_index(value: str) -> str:
    """HMAC determinista para buscar/deduplicar sin guardar el dato en claro."""
    return hmac.new(_index_key(), value.strip().lower().encode(), hashlib.sha256).hexdigest()


def token_hash(token: str) -> str:
    """Huella SHA-256 de tokens opacos (refresh, invitaciones): en BD nunca se guarda el token."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    user, domain = email.split("@", 1)
    return (user[:2] + "•" * max(1, len(user) - 2)) + "@" + domain
