from typing import Annotated

from fastapi import APIRouter, Query

from app.core.database import SessionDep
from app.modules.analytics import service
from app.modules.auth.deps import HR

router = APIRouter(prefix="/analytics", tags=["analítica"])


@router.get("/overview")
def overview(session: SessionDep, _: HR):
    return service.hr_overview(session)


@router.get("/skills")
def skills(session: SessionDep, _: HR, department: Annotated[str | None, Query(max_length=80)] = None,
           kind: Annotated[str | None, Query(pattern="^(tech|power)$")] = None, project_id: int | None = None):
    return service.skills_report(session, department or None, kind, project_id)


@router.get("/positions")
def positions(session: SessionDep, _: HR, project_id: int | None = None):
    return service.positions_report(session, project_id)


@router.get("/training")
def training(session: SessionDep, _: HR):
    return service.training_report(session)


@router.get("/filters")
def filters(session: SessionDep, _: HR):
    from sqlmodel import select

    from app.modules.projects.models import Project
    return {"departments": service.departments(session),
            "projects": [{"id": p.id, "name": p.name} for p in session.exec(select(Project)).all()]}
