"""Proyectos y cargos definidos por RR. HH. (Iteración 4 los tenía fijos en código)."""
import uuid
from datetime import datetime

from sqlmodel import JSON, Field, SQLModel

from app.core.time import utcnow

PROJECT_STATUS = ("planning", "active", "on_hold", "closed")
POSITION_STATUS = ("open", "closed")
REQ_KINDS = ("tech", "power", "certification")
IMPORTANCE = ("mandatory", "desirable")


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=20, unique=True)
    name: str = Field(max_length=120)
    area: str = Field(max_length=80)
    description: str = Field(default="", max_length=1200)
    status: str = Field(default="active", max_length=20)
    start_date: str | None = Field(default=None, max_length=10)
    end_date: str | None = Field(default=None, max_length=10)
    created_by: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Position(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=160)
    description: str = Field(default="", max_length=1500)
    seniority: str | None = Field(default=None, max_length=30)
    openings: int = 1
    min_years: float = 0
    min_years_mandatory: bool = False
    education_level: int = 0
    weights: dict = Field(default_factory=dict, sa_type=JSON)   # technical/power/experience/credentials
    status: str = Field(default="open", max_length=20, index=True)
    source_job_id: int | None = None                            # plantilla del dataset (si aplica)
    created_by: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PositionRequirement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="position.id", index=True, ondelete="CASCADE")
    kind: str = Field(max_length=20)          # tech | power | certification
    key: str = Field(max_length=120)
    name: str = Field(max_length=120)
    importance: str = Field(default="desirable", max_length=20)
    weight: float = 1.0                       # peso relativo dentro de su componente
