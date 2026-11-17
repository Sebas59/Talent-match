import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class AuditLog(SQLModel, table=True):
    """Bitácora sin datos personales con cadena de hashes (cada fila sella la anterior)."""
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    actor_id: uuid.UUID | None = Field(default=None, index=True)
    actor_role: str | None = Field(default=None, max_length=20)
    category: str = Field(default="data", max_length=20, index=True)  # auth|security|data|privacy|matching|admin|development
    action: str = Field(max_length=40, index=True)
    resource: str = Field(max_length=60)
    resource_id: str | None = Field(default=None, max_length=64)
    detail: str | None = Field(default=None, max_length=300)
    request_id: str | None = Field(default=None, max_length=32)
    ip_hash: str | None = Field(default=None, max_length=64)
    prev_hash: str = Field(max_length=64)
    hash: str = Field(max_length=64)
