"""Hashing de contraseñas y JWT (V5): https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

V6: el token de acceso incluye `sid` (sesión) para permitir revocación real en el servidor.
"""
import re
import uuid
from datetime import timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.time import utcnow

password_hash = PasswordHash.recommended()  # Argon2id
# Hash señuelo: verificar aunque el usuario no exista evita ataques de tiempo
DUMMY_HASH = password_hash.hash("timing-attack-dummy-password")

PASSWORD_RULES = "Mínimo 12 caracteres, con al menos una letra y un número."


def hash_password(plain: str) -> str:
    return password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def password_is_strong(plain: str) -> bool:
    return len(plain) >= 12 and re.search(r"[A-Za-z]", plain) is not None and re.search(r"\d", plain) is not None


def create_access_token(subject: str, role: str, session_id: str) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": subject,
        "role": role,
        "sid": session_id,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=s.access_token_expire_minutes),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.secret_key.get_secret_value(), algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(
        token,
        s.secret_key.get_secret_value(),
        algorithms=[s.jwt_algorithm],  # lista explícita: bloquea alg=none / confusión de algoritmo
        audience=s.jwt_audience,
        issuer=s.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "jti", "aud", "iss", "sid"]},
    )
