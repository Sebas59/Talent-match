from datetime import datetime

from sqlmodel import JSON, Field, SQLModel

from app.core.time import utcnow


class SystemSetting(SQLModel, table=True):
    key: str = Field(primary_key=True, max_length=60)
    value: dict = Field(default_factory=dict, sa_type=JSON)  # {"v": valor}
    updated_at: datetime = Field(default_factory=utcnow)
    updated_by: str | None = Field(default=None, max_length=64)
