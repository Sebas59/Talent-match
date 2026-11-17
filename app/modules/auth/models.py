"""Identidad, sesiones revocables e invitaciones.

V5 tenía un único rol efectivo (hr_admin). V6 define tres roles con permisos distintos.
El correo y el nombre se guardan cifrados; el login busca por índice ciego HMAC.
"""
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.time import utcnow

ROLES = ("employee", "hr", "admin")
ROLE_LABELS = {"employee": "Empleado", "hr": "Recursos Humanos", "admin": "Administrador"}


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email_index: str = Field(index=True, unique=True, max_length=64)  # HMAC del correo normalizado
    email_enc: str
    full_name_enc: str
    hashed_password: str
    role: str = Field(default="employee", max_length=20, index=True)
    department: str | None = Field(default=None, max_length=80)
    job_title: str | None = Field(default=None, max_length=120)
    is_active: bool = True
    is_demo: bool = False
    failed_attempts: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    invited_by: uuid.UUID | None = None


class AuthSession(SQLModel, table=True):
    """Sesión del usuario. El refresh token rota en cada uso; su reutilización revoca la sesión."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    refresh_hash: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked_at: datetime | None = None
    revoked_reason: str | None = Field(default=None, max_length=40)
    ip_hash: str | None = Field(default=None, max_length=64)


class Invitation(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token_hash: str = Field(index=True, unique=True, max_length=64)
    email_index: str = Field(index=True, max_length=64)
    email_enc: str
    full_name_enc: str
    role: str = Field(default="employee", max_length=20)
    department: str | None = Field(default=None, max_length=80)
    job_title: str | None = Field(default=None, max_length=120)
    invited_by: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    user_id: uuid.UUID | None = None
