import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import col, func, select

from app.core.config import get_settings
from app.core.crypto import decrypt
from app.core.database import SessionDep
from app.core.text import norm
from app.core.time import aware, utcnow
from app.modules.admin import settings as sysset
from app.modules.audit.models import AuditLog
from app.modules.audit.service import log_event, verify_chain
from app.modules.auth.deps import Admin
from app.modules.auth.models import ROLE_LABELS, AuthSession, User
from app.modules.auth.service import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["administración"])


class UserPatch(BaseModel):
    role: str | None = Field(default=None, pattern="^(employee|hr|admin)$")
    is_active: bool | None = None
    department: str | None = Field(default=None, max_length=80)
    job_title: str | None = Field(default=None, max_length=120)


class SettingsIn(BaseModel):
    values: dict[str, Any]


def _user_row(session, u: User) -> dict:
    active_sessions = session.exec(select(func.count()).select_from(AuthSession).where(
        AuthSession.user_id == u.id, AuthSession.revoked_at == None, AuthSession.expires_at > utcnow())).one()  # noqa: E711
    locked = aware(u.locked_until)
    return {"id": str(u.id), "full_name": decrypt(u.full_name_enc), "email": decrypt(u.email_enc), "role": u.role,
            "role_label": ROLE_LABELS[u.role], "department": u.department, "job_title": u.job_title,
            "is_active": u.is_active, "is_demo": u.is_demo, "locked": bool(locked and locked > utcnow()),
            "last_login_at": u.last_login_at, "created_at": u.created_at, "active_sessions": active_sessions}


@router.get("/users")
def users(session: SessionDep, _: Admin, q: Annotated[str, Query(max_length=60)] = "",
          role: Annotated[str | None, Query(pattern="^(employee|hr|admin)$")] = None):
    """Gestión de cuentas: identidad y rol. No incluye contenido de perfiles ni hojas de vida."""
    stmt = select(User).order_by(User.role, col(User.created_at))
    if role:
        stmt = stmt.where(User.role == role)
    rows = [_user_row(session, u) for u in session.exec(stmt).all()]
    if q:
        nq = norm(q)
        rows = [r for r in rows if nq in norm(f"{r['full_name']} {r['email']} {r['department'] or ''}")]
    return rows


@router.patch("/users/{user_id}")
def patch_user(user_id: uuid.UUID, body: UserPatch, request: Request, session: SessionDep, admin: Admin):
    u = session.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if u.id == admin.id and (body.role not in (None, "admin") or body.is_active is False):
        raise HTTPException(status_code=409, detail="No puede quitarse a sí mismo el rol de administrador ni desactivarse")
    changes = []
    if body.role and body.role != u.role:
        changes.append(f"rol:{u.role}->{body.role}")
        u.role = body.role
        revoke_all_sessions(session, u.id, "role_change")  # el nuevo rol aplica en el próximo inicio de sesión
    if body.is_active is not None and body.is_active != u.is_active:
        changes.append(f"activo:{body.is_active}")
        u.is_active = body.is_active
        if not body.is_active:
            revoke_all_sessions(session, u.id, "deactivated")
    for k in ("department", "job_title"):
        v = getattr(body, k)
        if v is not None:
            setattr(u, k, v or None)
    session.add(u)
    session.commit()
    log_event(session, actor=admin.id, actor_role=admin.role, action="user_updated", resource="user",
              resource_id=str(u.id), request=request, category="admin", detail="; ".join(changes) or None)
    return _user_row(session, u)


@router.post("/users/{user_id}/unlock")
def unlock(user_id: uuid.UUID, request: Request, session: SessionDep, admin: Admin):
    u = session.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u.locked_until, u.failed_attempts = None, 0
    session.add(u)
    session.commit()
    log_event(session, actor=admin.id, actor_role=admin.role, action="user_unlocked", resource="user",
              resource_id=str(u.id), request=request, category="security")
    return _user_row(session, u)


@router.post("/users/{user_id}/revoke-sessions")
def revoke(user_id: uuid.UUID, request: Request, session: SessionDep, admin: Admin):
    n = revoke_all_sessions(session, user_id, "admin_revoke")
    log_event(session, actor=admin.id, actor_role=admin.role, action="sessions_revoked", resource="user",
              resource_id=str(user_id), request=request, category="security", detail=f"sesiones={n}")
    return {"revoked": n}


@router.get("/settings")
def get_settings_(session: SessionDep, _: Admin):
    return {"values": sysset.all_settings(session), "descriptions": sysset.DESCRIPTIONS}


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, session: SessionDep, admin: Admin):
    from app.modules.matching.engine import normalize_weights

    changed = []
    for k, v in body.values.items():
        if k not in sysset.DEFAULTS or k == "session_idle_note":
            continue
        if k == "default_weights":
            if not isinstance(v, dict):
                raise HTTPException(status_code=422, detail="Ponderaciones inválidas")
            v = normalize_weights(v)
        elif k in ("availability_threshold", "min_confirmed_skills_to_publish", "retention_days"):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{k} debe ser numérico")
            limits = {"availability_threshold": (1, 100), "min_confirmed_skills_to_publish": (1, 20),
                      "retention_days": (30, 3650)}[k]
            if not limits[0] <= v <= limits[1]:
                raise HTTPException(status_code=422, detail=f"{k} fuera de rango {limits}")
        elif k == "external_ai_allowed":
            v = bool(v)
        elif k == "preferred_provider" and v not in ("auto", "anthropic", "gemini"):
            raise HTTPException(status_code=422, detail="Proveedor no válido")
        sysset.set_setting(session, k, v, str(admin.id))
        changed.append(k)
    session.commit()
    log_event(session, actor=admin.id, actor_role=admin.role, action="settings_updated", resource="settings",
              request=request, category="admin", detail=",".join(changed) or None)
    return {"values": sysset.all_settings(session), "descriptions": sysset.DESCRIPTIONS}


def system_status(session) -> dict:
    from app.modules.catalog.datasets import ALLOWED_COURSE_HOSTS  # noqa: F401
    from app.modules.extraction import providers
    from app.modules.extraction.document_reader import ocr_available

    s = get_settings()
    from app.main import catalog_state
    return {"version": s.app_version, "environment": s.environment, "database": s.database_url.split(":", 1)[0],
            "catalog": catalog_state(), "ocr_available": ocr_available(),
            "ai_providers_configured": providers.configured(), "ai_provider_mode": s.ai_provider,
            "demo_mode": s.demo_mode, "chain": verify_chain(session),
            "token_minutes": s.access_token_expire_minutes, "refresh_days": s.refresh_token_days,
            "rate_limit_per_minute": s.rate_limit_per_minute, "max_upload_mb": s.max_upload_mb,
            "cookie_secure": s.cookie_secure, "encryption_keys": len(s.field_encryption_key.get_secret_value().split(",")),
            "separate_blind_index_key": s.blind_index_key is not None}


@router.get("/system")
def system(session: SessionDep, _: Admin):
    return system_status(session)


@router.get("/security-events")
def security_events(session: SessionDep, _: Admin, days: Annotated[int, Query(ge=1, le=90)] = 7):
    since = utcnow() - timedelta(days=days)
    rows = session.exec(select(AuditLog).where(AuditLog.category == "security", AuditLog.ts >= since)
                        .order_by(col(AuditLog.id).desc()).limit(200)).all()
    return rows
