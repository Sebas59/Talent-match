"""Autenticación y autorización reutilizables. La autorización SIEMPRE se verifica aquí, en el servidor."""
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.database import SessionDep
from app.core.security import decode_access_token
from app.core.time import aware, utcnow
from app.modules.auth.models import AuthSession, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep, request: Request) -> User:
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        sid = uuid.UUID(payload["sid"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise CREDENTIALS_EXC
    sess = session.get(AuthSession, sid)
    # Revocación real: un token de una sesión cerrada deja de servir aunque no haya expirado
    if sess is None or sess.revoked_at is not None or sess.user_id != user_id or aware(sess.expires_at) < utcnow():
        raise CREDENTIALS_EXC
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXC
    request.state.user_id = user.id
    request.state.user_role = user.role
    request.state.session_id = sid
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    def checker(user: CurrentUser, request: Request, session: SessionDep) -> User:
        if user.role not in roles:
            from app.modules.audit.service import log_event

            log_event(session, actor=user.id, actor_role=user.role, action="forbidden", category="security",
                      resource=request.url.path[:60], request=request)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return user

    return checker


Employee = Annotated[User, Depends(require_role("employee"))]
HR = Annotated[User, Depends(require_role("hr"))]
Admin = Annotated[User, Depends(require_role("admin"))]
HROrAdmin = Annotated[User, Depends(require_role("hr", "admin"))]
