"""Perfil profesional propiedad del empleado.

Cada habilidad y cada entrada guarda su ORIGEN (extraída literal / inferida / IA externa / manual)
y su ESTADO (pendiente / confirmada / rechazada). Solo lo confirmado se publica y participa en el matching.
"""
import uuid
from datetime import datetime

from sqlmodel import JSON, Field, SQLModel

from app.core.time import utcnow

ORIGINS = ("extracted", "inferred", "ai_external", "manual")
STATUSES = ("pending", "confirmed", "rejected")


class Profile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", unique=True, index=True, ondelete="CASCADE")
    headline: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=1200)
    years_experience: float = 0
    years_source: str = Field(default="none", max_length=20)       # none | extracted | manual
    education_level: int = 0
    education_source: str = Field(default="none", max_length=20)
    status: str = Field(default="draft", max_length=20, index=True)  # draft | published
    published_at: datetime | None = None
    visibility: dict = Field(default_factory=lambda: {"summary": True, "experience": True, "education": True,
                                                      "certification": True, "language": True}, sa_type=JSON)
    open_to_mobility: bool = True
    last_source_type: str | None = Field(default=None, max_length=20)  # pdf-texto | pdf-escaneado | imagen | json
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ProfileSkill(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    kind: str = Field(max_length=10, index=True)        # tech | power
    key: str = Field(max_length=120, index=True)        # clave canónica (catálogo ES↔EN)
    name: str = Field(max_length=120)
    origin: str = Field(max_length=20)
    status: str = Field(default="pending", max_length=20, index=True)
    confidence: float | None = None                     # heurística, no probabilidad calibrada
    evidence: str | None = Field(default=None, max_length=300)
    source: str | None = Field(default=None, max_length=80)
    level: int | None = None                            # autovaloración 1-5 (opcional)
    extraction_id: int | None = Field(default=None, foreign_key="extractionrun.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=utcnow)
    confirmed_at: datetime | None = None


class ProfileEntry(SQLModel, table=True):
    """Experiencia, educación, certificación o idioma."""
    id: int | None = Field(default=None, primary_key=True)
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    kind: str = Field(max_length=20, index=True)  # experience | education | certification | language
    title: str = Field(max_length=200)
    organization: str | None = Field(default=None, max_length=160)
    start: str | None = Field(default=None, max_length=7)  # AAAA-MM
    end: str | None = Field(default=None, max_length=7)
    current: bool = False
    years: float | None = None
    level: str | None = Field(default=None, max_length=40)
    origin: str = Field(max_length=20)
    status: str = Field(default="pending", max_length=20)
    evidence: str | None = Field(default=None, max_length=300)
    extraction_id: int | None = Field(default=None, foreign_key="extractionrun.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=utcnow)


class ExtractionRun(SQLModel, table=True):
    """Trazabilidad del análisis de un CV. NO guarda el archivo ni su texto (minimización)."""
    id: int | None = Field(default=None, primary_key=True)
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    file_hash: str = Field(max_length=64)
    file_size: int
    source_type: str = Field(max_length=20)
    method: str = Field(max_length=160)
    provider: str = Field(max_length=20)               # local | anthropic | gemini
    provider_model: str | None = Field(default=None, max_length=60)
    external_used: bool = False
    pages: int = 1
    ocr_used: bool = False
    sensitive_categories: list[str] = Field(default_factory=list, sa_type=JSON)
    warnings: list[str] = Field(default_factory=list, sa_type=JSON)
    stats: dict = Field(default_factory=dict, sa_type=JSON)
    quality: dict = Field(default_factory=dict, sa_type=JSON)
    suggested: dict = Field(default_factory=dict, sa_type=JSON)  # años / nivel educativo sugeridos
    created_at: datetime = Field(default_factory=utcnow)
