from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WeightsIn(BaseModel):
    technical: float = Field(default=0.40, ge=0, le=1)
    power: float = Field(default=0.25, ge=0, le=1)
    experience: float = Field(default=0.20, ge=0, le=1)
    credentials: float = Field(default=0.15, ge=0, le=1)

    @field_validator("credentials")
    @classmethod
    def not_all_zero(cls, v, info):
        if v + sum(info.data.get(k, 0) for k in ("technical", "power", "experience")) <= 0:
            raise ValueError("Al menos una ponderación debe ser mayor que cero")
        return v


class RequirementIn(BaseModel):
    kind: str = Field(pattern="^(tech|power|certification)$")
    name: str = Field(min_length=1, max_length=120)
    importance: str = Field(default="desirable", pattern="^(mandatory|desirable)$")
    weight: float = Field(default=1.0, ge=0.1, le=3)


class RequirementOut(RequirementIn):
    id: int
    key: str


class ProjectIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    area: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=1200)
    status: str = Field(default="active", pattern="^(planning|active|on_hold|closed)$")
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1200)
    status: str | None = Field(default=None, pattern="^(planning|active|on_hold|closed)$")
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PositionIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1500)
    seniority: str | None = Field(default=None, max_length=30)
    openings: int = Field(default=1, ge=1, le=50)
    min_years: float = Field(default=0, ge=0, le=40)
    min_years_mandatory: bool = False
    education_level: int = Field(default=0, ge=0, le=7)
    weights: WeightsIn | None = None
    status: str = Field(default="open", pattern="^(open|closed)$")
    requirements: list[RequirementIn] = Field(default_factory=list, max_length=40)
    source_job_id: int | None = None


class PositionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=1500)
    seniority: str | None = Field(default=None, max_length=30)
    openings: int | None = Field(default=None, ge=1, le=50)
    min_years: float | None = Field(default=None, ge=0, le=40)
    min_years_mandatory: bool | None = None
    education_level: int | None = Field(default=None, ge=0, le=7)
    weights: WeightsIn | None = None
    status: str | None = Field(default=None, pattern="^(open|closed)$")
    requirements: list[RequirementIn] | None = Field(default=None, max_length=40)


class PositionOut(BaseModel):
    id: int
    project_id: int
    project_name: str
    project_code: str
    title: str
    description: str
    seniority: str | None
    openings: int
    min_years: float
    min_years_mandatory: bool
    education_level: int
    education_label: str
    weights: dict
    status: str
    source_job_id: int | None
    requirements: list[RequirementOut]
    created_at: datetime
    last_run: dict | None = None
    decisions: int = 0


class ProjectOut(BaseModel):
    id: int
    code: str
    name: str
    area: str
    description: str
    status: str
    start_date: str | None
    end_date: str | None
    created_at: datetime
    positions: list[PositionOut] = []
    open_positions: int = 0
