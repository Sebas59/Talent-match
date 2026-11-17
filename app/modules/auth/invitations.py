"""Invitaciones: RR. HH. invita empleados; el administrador puede invitar cualquier rol.

El token se muestra una sola vez (en producción se enviaría por correo); en BD solo queda su huella.
"""
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import col, select

from app.core.config import get_settings
from app.core.crypto import blind_index, decrypt, encrypt, mask_email, new_token, token_hash
from app.core.database import SessionDep
from app.core.security import PASSWORD_RULES, password_is_strong
from app.core.time import aware, utcnow
from app.modules.audit.service import log_event
from app.modules.auth import service
from app.modules.auth.deps import HROrAdmin
from app.modules.auth.models import ROLE_LABELS, Invitation
from app.modules.auth.schemas import InvitationAccept, InvitationCreate, InvitationOut, InvitationPreview

router = APIRouter(prefix="/invitations", tags=["invitaciones"])


def _status(inv: Invitation) -> str:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if aware(inv.expires_at) < utcnow():
        return "expired"
    return "pending"


def _out(inv: Invitation, url: str | None = None) -> InvitationOut:
    return InvitationOut(id=inv.id, email=decrypt(inv.email_enc) or "—", full_name=decrypt(inv.full_name_enc) or "—",
                         role=inv.role, department=inv.department, job_title=inv.job_title, created_at=inv.created_at,
                         expires_at=inv.expires_at, accepted_at=inv.accepted_at, revoked_at=inv.revoked_at,
                         status=_status(inv), invite_url=url)


@router.post("", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(body: InvitationCreate, request: Request, session: SessionDep, user: HROrAdmin):
    if user.role == "hr" and body.role != "employee":
        raise HTTPException(status_code=403, detail="Recursos Humanos solo puede invitar empleados")
    if service.find_by_email(session, body.email):
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo")
    idx = blind_index(body.email)
    for old in session.exec(select(Invitation).where(Invitation.email_index == idx, Invitation.accepted_at == None,  # noqa: E711
                                                     Invitation.revoked_at == None)).all():  # noqa: E711
        old.revoked_at = utcnow()  # solo una invitación vigente por correo
        session.add(old)
    raw = new_token()
    inv = Invitation(token_hash=token_hash(raw), email_index=idx, email_enc=encrypt(str(body.email).lower()),
                     full_name_enc=encrypt(body.full_name.strip()), role=body.role, department=body.department,
                     job_title=body.job_title, invited_by=user.id,
                     expires_at=utcnow() + timedelta(days=get_settings().invitation_days))
    session.add(inv)
    session.commit()
    session.refresh(inv)
    log_event(session, actor=user.id, actor_role=user.role, action="invitation_created", resource="invitation",
              resource_id=str(inv.id), request=request, category="admin", detail=f"rol={body.role}")
    return _out(inv, f"/invite/{raw}")


@router.get("", response_model=list[InvitationOut])
def list_invitations(session: SessionDep, user: HROrAdmin,
                     limit: Annotated[int, Query(ge=1, le=200)] = 100):
    q = select(Invitation).order_by(col(Invitation.created_at).desc()).limit(limit)
    if user.role == "hr":
        q = q.where(Invitation.role == "employee")
    return [_out(i) for i in session.exec(q).all()]


@router.delete("/{invitation_id}", status_code=204)
def revoke_invitation(invitation_id: uuid.UUID, request: Request, session: SessionDep, user: HROrAdmin):
    inv = session.get(Invitation, invitation_id)
    if inv is None or (user.role == "hr" and inv.role != "employee"):
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    if inv.accepted_at is None and inv.revoked_at is None:
        inv.revoked_at = utcnow()
        session.add(inv)
        session.commit()
        log_event(session, actor=user.id, actor_role=user.role, action="invitation_revoked", resource="invitation",
                  resource_id=str(inv.id), request=request, category="admin")


def _valid(session, token: str) -> Invitation:
    inv = session.exec(select(Invitation).where(Invitation.token_hash == token_hash(token))).first()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    st = _status(inv)
    if st != "pending":
        raise HTTPException(status_code=410, detail={"accepted": "La invitación ya fue utilizada",
                                                     "revoked": "La invitación fue revocada",
                                                     "expired": "La invitación expiró"}[st])
    return inv


@router.get("/token/{token}", response_model=InvitationPreview)
def preview(token: str, session: SessionDep):
    inv = _valid(session, token)
    return InvitationPreview(email_masked=mask_email(decrypt(inv.email_enc)) or "—",
                             full_name=decrypt(inv.full_name_enc) or "—", role=inv.role,
                             role_label=ROLE_LABELS.get(inv.role, inv.role),
                             organization=get_settings().organization_name, expires_at=inv.expires_at)


@router.post("/token/{token}/accept", status_code=201)
def accept(token: str, body: InvitationAccept, request: Request, session: SessionDep):
    inv = _valid(session, token)
    if not password_is_strong(body.password):
        raise HTTPException(status_code=422, detail=PASSWORD_RULES)
    email = decrypt(inv.email_enc)
    if not email or service.find_by_email(session, email):
        raise HTTPException(status_code=409, detail="La cuenta ya existe")
    user = service.create_user(session, email=email, full_name=decrypt(inv.full_name_enc) or "", password=body.password,
                               role=inv.role, department=inv.department, job_title=inv.job_title,
                               invited_by=inv.invited_by, commit=False)
    inv.accepted_at, inv.user_id = utcnow(), user.id
    session.add(inv)
    session.commit()
    log_event(session, actor=user.id, actor_role=user.role, action="invitation_accepted", resource="invitation",
              resource_id=str(inv.id), request=request, category="auth")
    return {"detail": "Cuenta creada. Ya puede iniciar sesión.", "email": email}
