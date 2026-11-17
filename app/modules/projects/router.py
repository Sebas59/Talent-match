from fastapi import APIRouter, Request
from sqlmodel import col, select

from app.core.database import SessionDep
from app.modules.audit.service import log_event
from app.modules.auth.deps import HR
from app.modules.matching.engine import normalize_weights
from app.modules.projects import service
from app.modules.projects.models import Position, Project
from app.modules.projects.schemas import PositionIn, PositionOut, PositionPatch, ProjectIn, ProjectOut, ProjectPatch

router = APIRouter(tags=["proyectos"])


def _audit(session, user, action, request, rid, resource="project", detail=None):
    log_event(session, actor=user.id, actor_role=user.role, action=action, resource=resource, resource_id=str(rid),
              request=request, category="matching", detail=detail)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: SessionDep, _: HR):
    rows = session.exec(select(Project).order_by(col(Project.created_at).desc())).all()
    return [service.project_out(session, p) for p in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, request: Request, session: SessionDep, user: HR):
    p = Project(code=service.next_code(session), created_by=user.id, **body.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    _audit(session, user, "project_created", request, p.id)
    return service.project_out(session, p)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: SessionDep, _: HR):
    return service.project_out(session, service.get_project(session, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def patch_project(project_id: int, body: ProjectPatch, request: Request, session: SessionDep, user: HR):
    p = service.get_project(session, project_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    service.touch(session, p)
    session.commit()
    _audit(session, user, "project_updated", request, p.id)
    return service.project_out(session, p)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, request: Request, session: SessionDep, user: HR):
    p = service.get_project(session, project_id)
    session.delete(p)
    session.commit()
    _audit(session, user, "project_deleted", request, project_id)


@router.post("/projects/{project_id}/positions", response_model=PositionOut, status_code=201)
def create_position(project_id: int, body: PositionIn, request: Request, session: SessionDep, user: HR):
    project = service.get_project(session, project_id)
    data = body.model_dump(exclude={"requirements", "weights"})
    weights = normalize_weights(body.weights.model_dump()) if body.weights else service.default_weights(session)
    pos = Position(project_id=project.id, created_by=user.id, weights=weights, **data)
    session.add(pos)
    session.flush()
    service.set_requirements(session, pos, body.requirements)
    session.commit()
    session.refresh(pos)
    _audit(session, user, "position_created", request, pos.id, resource="position")
    return service.position_out(session, pos, project)


@router.get("/positions", response_model=list[PositionOut])
def list_positions(session: SessionDep, _: HR, status: str | None = None):
    q = select(Position).order_by(col(Position.created_at).desc())
    if status in ("open", "closed"):
        q = q.where(Position.status == status)
    return [service.position_out(session, p) for p in session.exec(q).all()]


@router.get("/positions/{position_id}", response_model=PositionOut)
def get_position(position_id: int, session: SessionDep, _: HR):
    return service.position_out(session, service.get_position(session, position_id))


@router.patch("/positions/{position_id}", response_model=PositionOut)
def patch_position(position_id: int, body: PositionPatch, request: Request, session: SessionDep, user: HR):
    pos = service.get_position(session, position_id)
    data = body.model_dump(exclude_unset=True, exclude={"requirements", "weights"})
    for k, v in data.items():
        setattr(pos, k, v)
    if body.weights is not None:
        pos.weights = normalize_weights(body.weights.model_dump())
    if body.requirements is not None:
        service.set_requirements(session, pos, body.requirements)
    service.touch(session, pos)
    session.commit()
    _audit(session, user, "position_updated", request, pos.id, resource="position")
    return service.position_out(session, pos)


@router.delete("/positions/{position_id}", status_code=204)
def delete_position(position_id: int, request: Request, session: SessionDep, user: HR):
    session.delete(service.get_position(session, position_id))
    session.commit()
    _audit(session, user, "position_deleted", request, position_id, resource="position")
