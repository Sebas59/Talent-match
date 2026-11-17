import uuid
from datetime import datetime

from sqlmodel import JSON, Field, SQLModel

from app.core.time import utcnow

DECISIONS = ("shortlisted", "interview", "selected", "on_hold", "not_selected")
DECISION_LABELS = {"shortlisted": "Preseleccionado", "interview": "Entrevista", "selected": "Seleccionado",
                   "on_hold": "En espera", "not_selected": "No seleccionado"}


class MatchRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="position.id", index=True, ondelete="CASCADE")
    run_by: uuid.UUID = Field(foreign_key="user.id")
    weights: dict = Field(default_factory=dict, sa_type=JSON)
    engine_version: str = Field(default="v6-explainable-1", max_length=30)
    evaluated: int = 0
    eligible: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class MatchResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="matchrun.id", index=True, ondelete="CASCADE")
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    rank: int
    score: float
    eligible: bool
    components: dict = Field(default_factory=dict, sa_type=JSON)
    details: dict = Field(default_factory=dict, sa_type=JSON)  # coincidencias, brechas, evidencias, explicación


class HRDecision(SQLModel, table=True):
    """Supervisión humana: la IA recomienda, una persona decide y justifica."""
    id: int | None = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="position.id", index=True, ondelete="CASCADE")
    profile_id: uuid.UUID = Field(foreign_key="profile.id", index=True, ondelete="CASCADE")
    match_result_id: int | None = Field(default=None, foreign_key="matchresult.id", ondelete="SET NULL")
    decision: str = Field(max_length=20)
    justification: str = Field(max_length=1000)
    score_at_decision: float | None = None
    decided_by: uuid.UUID = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
