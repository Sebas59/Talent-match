import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.core.crypto import blind_index, decrypt, encrypt
from app.core.database import SessionDep
from app.core.time import utcnow
from app.modules.audit.service import log_event
from app.modules.auth.deps import Admin, Employee
from app.modules.auth.models import User
from app.modules.privacy.models import REQUEST_LABELS, PrivacyRequest

router = APIRouter(prefix="/privacy", tags=["privacidad"])


class RequestIn(BaseModel):
    type: str = Field(pattern="^(access|rectification|deletion|revocation|objection)$")
    detail: str = Field(default="", max_length=1000)


class ResolveIn(BaseModel):
    status: str = Field(pattern="^(in_progress|resolved|rejected)$")
    resolution: str = Field(min_length=5, max_length=1000)
    execute: bool = False  # ejecuta la acción asociada (supresión / revocatoria)


def _out(r: PrivacyRequest, session=None, with_user: bool = False) -> dict:
    out = {"id": str(r.id), "type": r.type, "type_label": REQUEST_LABELS[r.type], "status": r.status,
           "detail": decrypt(r.detail_enc), "resolution": decrypt(r.resolution_enc), "created_at": r.created_at,
           "resolved_at": r.resolved_at}
    if with_user and session is not None:
        u = session.get(User, r.user_id) if r.user_id else None
        out["requester"] = decrypt(u.full_name_enc) if u else "Cuenta eliminada"
        out["requester_email"] = decrypt(u.email_enc) if u else None
    return out


@router.post("/requests", status_code=201)
def create_request(body: RequestIn, request: Request, session: SessionDep, user: Employee):
    r = PrivacyRequest(user_id=user.id, type=body.type, detail_enc=encrypt(body.detail) if body.detail else None)
    session.add(r)
    session.commit()
    session.refresh(r)
    log_event(session, actor=user.id, actor_role=user.role, action="privacy_request", resource="privacy_request",
              resource_id=str(r.id), request=request, category="privacy", detail=f"tipo={body.type}")
    return _out(r)


@router.get("/requests/me")
def my_requests(session: SessionDep, user: Employee):
    rows = session.exec(select(PrivacyRequest).where(PrivacyRequest.user_id == user.id)
                        .order_by(col(PrivacyRequest.created_at).desc())).all()
    return [_out(r) for r in rows]


@router.get("/requests")
def all_requests(session: SessionDep, _: Admin, status: str | None = None):
    q = select(PrivacyRequest).order_by(col(PrivacyRequest.created_at).desc())
    if status:
        q = q.where(PrivacyRequest.status == status)
    return [_out(r, session, with_user=True) for r in session.exec(q).all()]


@router.patch("/requests/{request_id}")
def resolve(request_id: uuid.UUID, body: ResolveIn, request: Request, session: SessionDep, user: Admin):
    """El administrador gestiona la solicitud. Ejecutar una supresión borra el contenido del perfil
    sin que el administrador lo lea."""
    r = session.get(PrivacyRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    executed = None
    if body.execute and body.status == "resolved" and r.user_id:
        owner = session.get(User, r.user_id)
        if owner and r.type in ("deletion", "revocation"):
            from app.modules.consent import service as consent
            from app.modules.profiles import service as profiles

            consent.record(session, owner.id, False, False, blind_index(request.client.host) if request.client else None)
            prof = profiles.get_or_create(session, owner)
            if r.type == "deletion":
                profiles.wipe_profile_data(session, prof)
                executed = "profile_data_wiped"
            else:
                profiles.unpublish(session, prof)
                executed = "consent_revoked"
    r.status, r.resolution_enc = body.status, encrypt(body.resolution)
    r.resolved_at, r.resolved_by = (utcnow(), user.id) if body.status in ("resolved", "rejected") else (None, None)
    session.add(r)
    session.commit()
    log_event(session, actor=user.id, actor_role=user.role, action="privacy_request_" + body.status,
              resource="privacy_request", resource_id=str(r.id), request=request, category="privacy",
              detail=f"ejecutado={executed}" if executed else None)
    return _out(r, session, with_user=True)
