from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.core.config import get_settings
from app.core.crypto import blind_index
from app.core.database import SessionDep
from app.core.security import PASSWORD_RULES, hash_password, password_is_strong, verify_password
from app.modules.audit.service import log_event
from app.modules.auth import service
from app.core.time import utcnow
from app.modules.auth.deps import CREDENTIALS_EXC, CurrentUser
from app.modules.auth.models import AuthSession
from app.modules.auth.schemas import PasswordChange, Token, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE_PATH = "/api/v1/auth"


def _set_refresh(response: Response, value: str) -> None:
    s = get_settings()
    response.set_cookie(service.REFRESH_COOKIE, value, max_age=s.refresh_token_days * 86400, httponly=True,
                        secure=s.cookie_secure, samesite="strict", path=COOKIE_PATH)


def _ip_hash(request: Request) -> str | None:
    return blind_index(request.client.host) if request.client else None


@router.post("/token", response_model=Token)
def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],  # credenciales en el body, nunca en la URL
    session: SessionDep,
) -> Token:
    user, reason = service.authenticate(session, form.username, form.password)
    if user is None:
        log_event(session, actor=None, action="login_failed", resource="auth", request=request,
                  category="security", detail=f"motivo={reason}")
        if reason == "lockout":
            log_event(session, actor=None, action="account_locked", resource="auth", request=request,
                      category="security")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=CREDENTIALS_EXC.detail,
                            headers=CREDENTIALS_EXC.headers)
    _, access, refresh = service.open_session(session, user, _ip_hash(request))
    log_event(session, actor=user.id, actor_role=user.role, action="login_ok", resource="auth",
              request=request, category="auth")
    _set_refresh(response, refresh)
    return Token(access_token=access, expires_in=get_settings().access_token_expire_minutes * 60,
                 user=service.to_public(user))


@router.post("/refresh", response_model=Token, responses={204: {"description": "Sin sesión"}})
def refresh(request: Request, response: Response, session: SessionDep,
            tm_refresh: Annotated[str | None, Cookie()] = None,
            x_tm_refresh: Annotated[str | None, Header()] = None) -> Token:
    """Renueva el token de acceso. Exige cabecera propia (un formulario de otro sitio no puede enviarla)."""
    if x_tm_refresh != "1":
        raise HTTPException(status_code=401, detail="Sesión no disponible")
    if not tm_refresh:
        return Response(status_code=204)  # no hay sesión que renovar (visitante sin iniciar sesión)
    try:
        user, access, new_refresh = service.rotate_session(session, tm_refresh)
    except HTTPException:
        response.delete_cookie(service.REFRESH_COOKIE, path=COOKIE_PATH)
        log_event(session, actor=None, action="refresh_rejected", resource="auth", request=request, category="security")
        raise
    _set_refresh(response, new_refresh)
    return Token(access_token=access, expires_in=get_settings().access_token_expire_minutes * 60,
                 user=service.to_public(user))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user: CurrentUser, session: SessionDep):
    service.revoke_session(session, request.state.session_id, "logout")
    response.delete_cookie(service.REFRESH_COOKIE, path=COOKIE_PATH)
    log_event(session, actor=user.id, actor_role=user.role, action="logout", resource="auth", request=request,
              category="auth")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser):
    return service.to_public(user)


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, request: Request, user: CurrentUser, session: SessionDep):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    if not password_is_strong(body.new_password):
        raise HTTPException(status_code=422, detail=PASSWORD_RULES)
    user.hashed_password = hash_password(body.new_password)
    session.add(user)
    session.commit()
    # Cierra las demás sesiones abiertas del usuario
    current = request.state.session_id
    for other in session.exec(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != current,
                                                        AuthSession.revoked_at == None)).all():  # noqa: E711
        other.revoked_at, other.revoked_reason = utcnow(), "password_change"
        session.add(other)
    session.commit()
    log_event(session, actor=user.id, actor_role=user.role, action="password_changed", resource="auth",
              request=request, category="security")
    return Response(status_code=204)
