import uuid

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.time import utcnow
from app.modules.consent.models import Consent
from app.modules.consent.policy import EXTERNAL_AI_PURPOSE, PURPOSES


def current(session: Session, user_id: uuid.UUID) -> Consent | None:
    return session.exec(select(Consent).where(Consent.user_id == user_id, Consent.revoked_at == None)  # noqa: E711
                        .order_by(col(Consent.granted_at).desc())).first()


def has_processing(session: Session, user_id: uuid.UUID) -> bool:
    c = current(session, user_id)
    return bool(c and c.processing)


def record(session: Session, user_id: uuid.UUID, processing: bool, external_ai: bool, ip_hash: str | None) -> Consent:
    now = utcnow()
    prev = current(session, user_id)
    if prev:
        prev.revoked_at = now
        session.add(prev)
    purposes = list(PURPOSES) if processing else []
    if processing and external_ai:
        purposes.append(EXTERNAL_AI_PURPOSE)
    c = Consent(user_id=user_id, policy_version=get_settings().consent_policy_version, processing=processing,
                external_ai=bool(processing and external_ai), purposes=purposes, evidence_ip_hash=ip_hash)
    session.add(c)
    session.flush()
    return c


def history(session: Session, user_id: uuid.UUID) -> list[Consent]:
    return list(session.exec(select(Consent).where(Consent.user_id == user_id).order_by(col(Consent.granted_at).desc())))
