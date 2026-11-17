import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SkillOut(BaseModel):
    id: int
    kind: str
    key: str
    name: str
    origin: str
    status: str
    confidence: float | None = None
    confidence_label: str | None = None
    evidence: str | None = None
    source: str | None = None
    level: int | None = None


class EntryOut(BaseModel):
    id: int
    kind: str
    title: str
    organization: str | None = None
    start: str | None = None
    end: str | None = None
    current: bool = False
    years: float | None = None
    level: str | None = None
    origin: str
    status: str
    evidence: str | None = None


class ExtractionOut(BaseModel):
    id: int
    created_at: datetime
    source_type: str
    method: str
    provider: str
    provider_model: str | None
    external_used: bool
    pages: int
    ocr_used: bool
    sensitive_categories: list[str]
    warnings: list[str]
    stats: dict
    quality: dict
    suggested: dict
    file_size: int


class ProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str | None = None
    department: str | None = None
    job_title: str | None = None
    headline: str | None
    summary: str | None
    years_experience: float
    years_source: str
    education_level: int
    education_label: str
    education_source: str
    status: str
    published_at: datetime | None
    visibility: dict
    open_to_mobility: bool
    completeness: int
    completeness_breakdown: list[dict]
    skills: list[SkillOut]
    entries: list[EntryOut]
    updated_at: datetime
    last_extraction: ExtractionOut | None = None
    consent: dict | None = None
    can_publish: bool = False
    publish_blockers: list[str] = []


class ProfileUpdate(BaseModel):
    headline: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=1200)
    years_experience: float | None = Field(default=None, ge=0, le=60)
    education_level: int | None = Field(default=None, ge=0, le=7)
    visibility: dict[str, bool] | None = None
    open_to_mobility: bool | None = None


class SkillCreate(BaseModel):
    kind: str = Field(pattern="^(tech|power)$")
    name: str = Field(min_length=1, max_length=120)
    level: int | None = Field(default=None, ge=1, le=5)


class SkillPatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|confirmed|rejected)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    level: int | None = Field(default=None, ge=1, le=5)


class BulkConfirm(BaseModel):
    kind: str | None = Field(default=None, pattern="^(tech|power)$")
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    include_entries: bool = True


class EntryCreate(BaseModel):
    kind: str = Field(pattern="^(experience|education|certification|language)$")
    title: str = Field(min_length=2, max_length=200)
    organization: str | None = Field(default=None, max_length=160)
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    current: bool = False
    level: str | None = Field(default=None, max_length=40)


class EntryPatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|confirmed|rejected)$")
    title: str | None = Field(default=None, min_length=2, max_length=200)
    organization: str | None = Field(default=None, max_length=160)
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    current: bool | None = None
    level: str | None = Field(default=None, max_length=40)


class TalentCard(BaseModel):
    profile_id: uuid.UUID
    full_name: str
    department: str | None
    job_title: str | None
    headline: str | None
    years_experience: float
    education_label: str
    top_tech: list[str]
    top_power: list[str]
    tech_count: int
    power_count: int
    certifications: int
    completeness: int
    open_to_mobility: bool
    published_at: datetime | None
    active_paths: int = 0
