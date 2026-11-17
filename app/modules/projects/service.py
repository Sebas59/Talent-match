from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.core.text import norm
from app.core.time import utcnow
from app.modules.admin.settings import get_setting
from app.modules.catalog.skills import EDU_LEVELS, canonical_soft, canonical_tech, display_tech, soft_label
from app.modules.matching.engine import normalize_weights
from app.modules.projects.models import Position, PositionRequirement, Project
from app.modules.projects.schemas import PositionOut, ProjectOut, RequirementIn, RequirementOut


def requirement_key(kind: str, name: str) -> tuple[str, str]:
    if kind == "tech":
        key = canonical_tech(name)
        return key, display_tech(key)
    if kind == "power":
        sk = canonical_soft(name)
        return (sk, soft_label(sk)) if sk else (norm(name), name.strip())
    return norm(name), name.strip()


def set_requirements(session: Session, pos: Position, reqs: list[RequirementIn]) -> None:
    for old in session.exec(select(PositionRequirement).where(PositionRequirement.position_id == pos.id)):
        session.delete(old)
    seen = set()
    for r in reqs:
        key, label = requirement_key(r.kind, r.name)
        if not key or (r.kind, key) in seen:
            continue
        seen.add((r.kind, key))
        session.add(PositionRequirement(position_id=pos.id, kind=r.kind, key=key[:120], name=label[:120],
                                        importance=r.importance, weight=r.weight))


def requirements(session: Session, pos_id: int) -> list[PositionRequirement]:
    return list(session.exec(select(PositionRequirement).where(PositionRequirement.position_id == pos_id)
                             .order_by(PositionRequirement.kind, PositionRequirement.importance, PositionRequirement.id)))


def default_weights(session: Session) -> dict:
    return normalize_weights(get_setting(session, "default_weights"))


def position_out(session: Session, pos: Position, project: Project | None = None) -> PositionOut:
    from app.modules.matching.models import HRDecision, MatchRun

    project = project or session.get(Project, pos.project_id)
    run = session.exec(select(MatchRun).where(MatchRun.position_id == pos.id).order_by(col(MatchRun.id).desc())).first()
    n_dec = session.exec(select(func.count()).select_from(HRDecision).where(HRDecision.position_id == pos.id)).one()
    return PositionOut(
        id=pos.id, project_id=pos.project_id, project_name=project.name, project_code=project.code, title=pos.title,
        description=pos.description, seniority=pos.seniority, openings=pos.openings, min_years=pos.min_years,
        min_years_mandatory=pos.min_years_mandatory, education_level=pos.education_level,
        education_label=EDU_LEVELS.get(pos.education_level, "No especificado"), weights=pos.weights,
        status=pos.status, source_job_id=pos.source_job_id,
        requirements=[RequirementOut(id=r.id, kind=r.kind, key=r.key, name=r.name, importance=r.importance,
                                     weight=r.weight) for r in requirements(session, pos.id)],
        created_at=pos.created_at,
        last_run={"id": run.id, "created_at": run.created_at.isoformat(), "evaluated": run.evaluated,
                  "eligible": run.eligible} if run else None,
        decisions=n_dec,
    )


def project_out(session: Session, p: Project, with_positions: bool = True) -> ProjectOut:
    positions = list(session.exec(select(Position).where(Position.project_id == p.id).order_by(Position.id)))
    return ProjectOut(id=p.id, code=p.code, name=p.name, area=p.area, description=p.description, status=p.status,
                      start_date=p.start_date, end_date=p.end_date, created_at=p.created_at,
                      positions=[position_out(session, x, p) for x in positions] if with_positions else [],
                      open_positions=sum(1 for x in positions if x.status == "open"))


def next_code(session: Session) -> str:
    n = session.exec(select(func.count()).select_from(Project)).one()
    code = f"PRJ-{n + 1:03d}"
    while session.exec(select(Project).where(Project.code == code)).first():
        n += 1
        code = f"PRJ-{n + 1:03d}"
    return code


def get_project(session: Session, pid: int) -> Project:
    p = session.get(Project, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return p


def get_position(session: Session, pid: int) -> Position:
    p = session.get(Position, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")
    return p


def touch(session: Session, obj) -> None:
    obj.updated_at = utcnow()
    session.add(obj)
