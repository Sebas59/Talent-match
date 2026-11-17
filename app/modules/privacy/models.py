import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.time import utcnow

REQUEST_TYPES = ("access", "rectification", "deletion", "revocation", "objection")
REQUEST_LABELS = {"access": "Acceso / copia de datos", "rectification": "Rectificación", "deletion": "Supresión de datos",
                  "revocation": "Revocatoria de autorización", "objection": "Oposición / consulta"}
REQUEST_STATUS = ("open", "in_progress", "resolved", "rejected")


class PrivacyRequest(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True, ondelete="SET NULL")
    type: str = Field(max_length=20)
    status: str = Field(default="open", max_length=20, index=True)
    detail_enc: str | None = None            # texto libre del titular, cifrado
    resolution_enc: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
