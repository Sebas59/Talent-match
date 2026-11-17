import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    """Nunca exponer hashed_password: response_model filtra la salida."""
    id: uuid.UUID
    email: EmailStr | str
    full_name: str
    role: str
    role_label: str
    department: str | None = None
    job_title: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class InvitationCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    role: str = Field(default="employee", pattern="^(employee|hr|admin)$")
    department: str | None = Field(default=None, max_length=80)
    job_title: str | None = Field(default=None, max_length=120)


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    department: str | None
    job_title: str | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    status: str
    invite_url: str | None = None   # solo se devuelve al crearla (el token no se guarda)


class InvitationPreview(BaseModel):
    email_masked: str
    full_name: str
    role: str
    role_label: str
    organization: str
    expires_at: datetime


class InvitationAccept(BaseModel):
    password: str = Field(min_length=12, max_length=128)
