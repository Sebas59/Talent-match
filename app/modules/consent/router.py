from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.crypto import blind_index
from app.core.database import SessionDep
from app.modules.audit.service import log_event
from app.modules.auth.deps import CurrentUser, Employee
from app.modules.consent import service
from app.modules.consent.policy import policy_document

router = APIRouter(prefix="/consent", tags=["consentimiento"])


class ConsentIn(BaseModel):
    processing: bool
    external_ai: bool = False
    policy_version: str


def _out(c) -> dict:
    if c is None:
        return {"processing": False, "external_ai": False, "granted_at": None, "policy_version": None, "purposes": []}
    return {"processing": c.processing, "external_ai": c.external_ai, "granted_at": c.granted_at,
            "policy_version": c.policy_version, "purposes": c.purposes, "revoked_at": c.revoked_at}


@router.get("/policy")
def get_policy():
    """Aviso de privacidad público: se muestra ANTES de capturar el CV."""
    return policy_document()


@router.get("/me")
def my_consent(session: SessionDep, user: CurrentUser):
    return _out(service.current(session, user.id))


@router.get("/me/history")
def my_history(session: SessionDep, user: CurrentUser):
    return [_out(c) for c in service.history(session, user.id)]


@router.post("/me")
def set_consent(body: ConsentIn, request: Request, session: SessionDep, user: Employee):
    if body.policy_version != get_settings().consent_policy_version:
        raise HTTPException(status_code=409, detail="La política de tratamiento cambió; vuelva a leerla")
    c = service.record(session, user.id, body.processing, body.external_ai,
                       blind_index(request.client.host) if request.client else None)
    if not body.processing:
        # Revocar la autorización retira de inmediato el perfil del alcance de RR. HH.
        from app.modules.profiles import service as profiles

        prof = profiles.get_or_create(session, user)
        if prof.status == "published":
            profiles.unpublish(session, prof)
    session.commit()
    log_event(session, actor=user.id, actor_role=user.role, request=request, category="privacy",
              action="consent_granted" if body.processing else "consent_revoked", resource="consent",
              detail=f"ia_externa={c.external_ai}")
    return _out(c)
