import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.crypto import blind_index, decrypt, encrypt, new_token, token_hash
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.core.time import aware, utcnow
from app.modules.auth.models import ROLE_LABELS, AuthSession, User
from app.modules.auth.schemas import UserPublic

REFRESH_COOKIE = "tm_refresh"


def find_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email_index == blind_index(email))).first()


def authenticate(session: Session, email: str, password: str) -> tuple[User | None, str]:
    """Devuelve (usuario, motivo). Motivo para la auditoría: ok | unknown | locked | bad_password | inactive."""
    s = get_settings()
    user = find_by_email(session, email)
    if user is None:
        verify_password(password, DUMMY_HASH)  # tiempo constante
        return None, "unknown"
    now = utcnow()
    locked = aware(user.locked_until)
    if locked and locked > now:
        verify_password(password, DUMMY_HASH)
        return None, "locked"
    if not verify_password(password, user.hashed_password):
        user.failed_attempts += 1
        reason = "bad_password"
        if user.failed_attempts >= s.login_max_attempts:
            user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
            user.failed_attempts = 0
            reason = "lockout"
        session.add(user)
        session.commit()
        return None, reason
    if not user.is_active:
        return None, "inactive"
    user.failed_attempts, user.locked_until, user.last_login_at = 0, None, now
    session.add(user)
    session.commit()
    return user, "ok"


def create_user(session: Session, *, email: str, full_name: str, password: str, role: str,
                department: str | None = None, job_title: str | None = None, is_demo: bool = False,
                invited_by: uuid.UUID | None = None, commit: bool = True) -> User:
    user = User(email_index=blind_index(email), email_enc=encrypt(email.strip().lower()),
                full_name_enc=encrypt(full_name.strip()), hashed_password=hash_password(password), role=role,
                department=department, job_title=job_title, is_demo=is_demo, invited_by=invited_by)
    session.add(user)
    if commit:
        session.commit()
        session.refresh(user)
    else:
        session.flush()
    return user


def to_public(u: User) -> UserPublic:
    return UserPublic(id=u.id, email=decrypt(u.email_enc) or "—", full_name=decrypt(u.full_name_enc) or "—",
                      role=u.role, role_label=ROLE_LABELS.get(u.role, u.role), department=u.department,
                      job_title=u.job_title)


def display_name(u: User | None) -> str:
    return (decrypt(u.full_name_enc) or "—") if u else "—"


# ---------------------------------------------------------------------------
# Sesiones (refresh token opaco "<session_id>.<aleatorio>" en cookie HttpOnly)
# ---------------------------------------------------------------------------
def open_session(session: Session, user: User, ip_hash: str | None) -> tuple[AuthSession, str, str]:
    s = get_settings()
    raw = new_token()
    sess = AuthSession(user_id=user.id, refresh_hash=token_hash(raw), ip_hash=ip_hash,
                       expires_at=utcnow() + timedelta(days=s.refresh_token_days))
    session.add(sess)
    session.commit()
    session.refresh(sess)
    access = create_access_token(str(user.id), user.role, str(sess.id))
    return sess, access, f"{sess.id}.{raw}"


def rotate_session(session: Session, refresh_cookie: str) -> tuple[User, str, str]:
    try:
        sid_raw, raw = refresh_cookie.split(".", 1)
        sid = uuid.UUID(sid_raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    sess = session.get(AuthSession, sid)
    now = utcnow()
    if sess is None or sess.revoked_at is not None or aware(sess.expires_at) < now:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    if sess.refresh_hash != token_hash(raw):
        # Reutilización de un refresh ya rotado: posible robo -> se revoca la sesión completa
        sess.revoked_at, sess.revoked_reason = now, "refresh_reuse"
        session.add(sess)
        session.commit()
        raise HTTPException(status_code=401, detail="Sesión revocada por seguridad")
    user = session.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    new_raw = new_token()
    sess.refresh_hash, sess.last_used_at = token_hash(new_raw), now
    session.add(sess)
    session.commit()
    return user, create_access_token(str(user.id), user.role, str(sess.id)), f"{sess.id}.{new_raw}"


def revoke_session(session: Session, sid: uuid.UUID, reason: str = "logout") -> None:
    sess = session.get(AuthSession, sid)
    if sess and sess.revoked_at is None:
        sess.revoked_at, sess.revoked_reason = utcnow(), reason
        session.add(sess)
        session.commit()


def revoke_all_sessions(session: Session, user_id: uuid.UUID, reason: str) -> int:
    rows = session.exec(select(AuthSession).where(AuthSession.user_id == user_id,
                                                  AuthSession.revoked_at == None)).all()  # noqa: E711
    for r in rows:
        r.revoked_at, r.revoked_reason = utcnow(), reason
        session.add(r)
    session.commit()
    return len(rows)


def seed_admin(session: Session) -> None:
    """Crea el administrador inicial desde variables de entorno si aún no existe ninguno."""
    s = get_settings()
    if not s.admin_email or not s.admin_password:
        return
    if session.exec(select(User).where(User.role == "admin")).first():
        return
    if find_by_email(session, str(s.admin_email)):
        return
    create_user(session, email=str(s.admin_email), full_name="Administrador del sistema",
                password=s.admin_password.get_secret_value(), role="admin")
