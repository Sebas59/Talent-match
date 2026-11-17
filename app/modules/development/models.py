import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.time import utcnow

ITEM_STATUS = ("pending", "in_progress", "completed")


class LearningPath(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=160)
    position_id: int | None = Field(default=None, foreign_key="position.id", ondelete="SET NULL")
    assigned_by: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    self_assigned: bool = False
    status: str = Field(default="active", max_length=20)  # active | completed | archived
    due_date: str | None = Field(default=None, max_length=10)
    note: str | None = Field(default=None, max_length=400)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LearningItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    path_id: int = Field(foreign_key="learningpath.id", index=True, ondelete="CASCADE")
    skill: str = Field(max_length=120)
    skill_key: str = Field(max_length=120)
    skill_kind: str = Field(max_length=10)
    order: int = 0
    course_title: str | None = Field(default=None, max_length=300)
    platform: str | None = Field(default=None, max_length=20)
    provider: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    rating: float | None = None
    hours: float | None = None
    hours_estimated: bool = False
    level: str | None = Field(default=None, max_length=40)
    relevance: float | None = None
    status: str = Field(default="pending", max_length=20)
    progress: int = 0
    completed_at: datetime | None = None
