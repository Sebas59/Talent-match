from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import col, select

from app.core.database import SessionDep
from app.modules.audit.models import AuditLog
from app.modules.audit.service import verify_chain
from app.modules.auth.deps import Admin

router = APIRouter(prefix="/audit", tags=["auditoría"])


@router.get("")
def list_audit(session: SessionDep, _: Admin, limit: Annotated[int, Query(ge=1, le=500)] = 100,
               category: Annotated[str | None, Query(max_length=20)] = None,
               action: Annotated[str | None, Query(max_length=40)] = None,
               before_id: int | None = None):
    q = select(AuditLog).order_by(col(AuditLog.id).desc()).limit(limit)
    if category:
        q = q.where(AuditLog.category == category)
    if action:
        q = q.where(AuditLog.action == action)
    if before_id:
        q = q.where(AuditLog.id < before_id)
    return session.exec(q).all()


@router.get("/verify")
def verify(session: SessionDep, _: Admin):
    return verify_chain(session)
