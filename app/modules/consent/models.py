import uuid
from datetime import datetime

from sqlmodel import JSON, Field, SQLModel

from app.core.time import utcnow


class Consent(SQLModel, table=True):
    """Prueba de la autorización otorgada POR EL TITULAR (V5 la registraba RR. HH. en su nombre).

    Cada cambio crea un registro nuevo y cierra el anterior: queda el historial completo.
    `external_ai` es una autorización separada para proveedores externos de IA.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True, foreign_key="user.id", ondelete="CASCADE")
    policy_version: str = Field(max_length=20)
    processing: bool = False            # tratamiento de datos para gestión de talento interno
    external_ai: bool = False           # envío de texto anonimizado a un proveedor externo de IA
    purposes: list[str] = Field(default_factory=list, sa_type=JSON)
    granted_at: datetime = Field(default_factory=utcnow)
    revoked_at: datetime | None = None   # se llena cuando lo reemplaza otro registro
    evidence_ip_hash: str | None = Field(default=None, max_length=64)
