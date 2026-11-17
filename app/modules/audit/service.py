"""Registro de auditoría con cadena de hashes (V6). Nunca se guardan datos personales en `detail`.

hash_n = SHA-256(prev_hash || ts || actor || rol || categoría || acción || recurso || id || detalle)
Alterar o borrar una fila rompe la cadena y `verify_chain` lo detecta.
Limitación: en PostgreSQL con escrituras concurrentes se debe serializar la inserción (bloqueo asesor).
"""
import hashlib
import json
import uuid

from fastapi import Request
from sqlmodel import Session, col, select

from app.core.crypto import blind_index
from app.core.time import aware
from app.modules.audit.models import AuditLog

GENESIS = "0" * 64


def _digest(row: AuditLog) -> str:
    ts = aware(row.ts).isoformat(timespec="microseconds")
    payload = json.dumps([row.prev_hash, ts, str(row.actor_id) if row.actor_id else None, row.actor_role,
                          row.category, row.action, row.resource, row.resource_id, row.detail],
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def log_event(session: Session, *, actor: uuid.UUID | None, action: str, resource: str,
              resource_id: str | None = None, request: Request | None = None, category: str = "data",
              detail: str | None = None, actor_role: str | None = None, commit: bool = True) -> AuditLog:
    ip = request.client.host if request and request.client else None
    last = session.exec(select(AuditLog).order_by(col(AuditLog.id).desc()).limit(1)).first()
    row = AuditLog(
        actor_id=actor, actor_role=actor_role, category=category, action=action, resource=resource,
        resource_id=resource_id, detail=(detail or None) and detail[:300],
        request_id=getattr(request.state, "request_id", None) if request else None,
        ip_hash=blind_index(ip) if ip else None,  # IP seudonimizada
        prev_hash=last.hash if last else GENESIS, hash="",
    )
    row.hash = _digest(row)
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    return row


def verify_chain(session: Session) -> dict:
    prev = GENESIS
    checked = 0
    for row in session.exec(select(AuditLog).order_by(col(AuditLog.id))):
        if row.prev_hash != prev or _digest(row) != row.hash:
            return {"valid": False, "checked": checked, "broken_at": row.id}
        prev = row.hash
        checked += 1
    return {"valid": True, "checked": checked, "broken_at": None, "head": prev}
