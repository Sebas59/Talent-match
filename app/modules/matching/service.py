from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.crypto import decrypt
from app.modules.auth.models import User
from app.modules.matching.engine import Candidate, PositionSpec, Requirement, evaluate, normalize_weights
from app.modules.matching.models import DECISION_LABELS, HRDecision, MatchResult, MatchRun
from app.modules.profiles import service as profiles
from app.modules.profiles.models import Profile
from app.modules.projects import service as projects
from app.modules.projects.models import Position, Project


def candidate_from_profile(session: Session, prof: Profile) -> Candidate:
    """Solo información CONFIRMADA por el empleado participa en el matching."""
    skills = profiles.skills_of(session, prof.id, confirmed_only=True)
    entries = profiles.entries_of(session, prof.id, confirmed_only=True)
    pack = lambda s: {"name": s.name, "evidence": s.evidence, "origin": s.origin}  # noqa: E731
    return Candidate(tech={s.key: pack(s) for s in skills if s.kind == "tech"},
                     power={s.key: pack(s) for s in skills if s.kind == "power"},
                     certifications=[e.title for e in entries if e.kind == "certification"],
                     years=float(prof.years_experience or 0), edu_level=int(prof.education_level or 0))


def spec_from_position(session: Session, pos: Position, weights: dict | None = None) -> PositionSpec:
    reqs = [Requirement(kind=r.kind, key=r.key, name=r.name, importance=r.importance, weight=r.weight)
            for r in projects.requirements(session, pos.id)]
    return PositionSpec(requirements=reqs, weights=normalize_weights(weights or pos.weights), min_years=pos.min_years,
                        min_years_mandatory=pos.min_years_mandatory, education_level=pos.education_level)


def run_match(session: Session, pos: Position, user: User, weights: dict | None = None) -> MatchRun:
    spec = spec_from_position(session, pos, weights)
    if not spec.requirements:
        raise HTTPException(status_code=422, detail="El cargo no tiene requisitos definidos")
    pool = profiles.published_profiles(session)
    scored = []
    for prof, _u in pool:
        scored.append((prof, evaluate(candidate_from_profile(session, prof), spec)))
    # Primero quienes cumplen los obligatorios; luego por puntaje
    scored.sort(key=lambda x: (not x[1]["eligible"], -x[1]["score"]))
    run = MatchRun(position_id=pos.id, run_by=user.id, weights=spec.weights, evaluated=len(scored),
                   eligible=sum(1 for _, r in scored if r["eligible"]))
    session.add(run)
    session.flush()
    for rank, (prof, res) in enumerate(scored, start=1):
        session.add(MatchResult(run_id=run.id, profile_id=prof.id, rank=rank, score=res["score"],
                                eligible=res["eligible"], components=res["components"],
                                details={k: v for k, v in res.items() if k not in ("score", "eligible", "components")}))
    session.commit()
    session.refresh(run)
    return run


def latest_run(session: Session, position_id: int) -> MatchRun | None:
    return session.exec(select(MatchRun).where(MatchRun.position_id == position_id)
                        .order_by(col(MatchRun.id).desc())).first()


def _decision_map(session: Session, position_id: int) -> dict[uuid.UUID, HRDecision]:
    out: dict[uuid.UUID, HRDecision] = {}
    for d in session.exec(select(HRDecision).where(HRDecision.position_id == position_id)
                          .order_by(col(HRDecision.created_at))):
        out[d.profile_id] = d  # la más reciente prevalece
    return out


def result_out(session: Session, r: MatchResult, decisions: dict | None = None) -> dict:
    prof = session.get(Profile, r.profile_id)
    user = session.get(User, prof.user_id) if prof else None
    d = (decisions or {}).get(r.profile_id)
    return {
        "id": r.id, "run_id": r.run_id, "profile_id": str(r.profile_id), "rank": r.rank, "score": r.score,
        "eligible": r.eligible, "components": r.components, **r.details,
        "full_name": decrypt(user.full_name_enc) if user else "—", "department": user.department if user else None,
        "job_title": user.job_title if user else None, "headline": prof.headline if prof else None,
        "years_experience": prof.years_experience if prof else 0,
        "still_published": bool(prof and prof.status == "published"),
        "decision": {"decision": d.decision, "label": DECISION_LABELS[d.decision], "created_at": d.created_at.isoformat()}
        if d else None,
    }


def run_out(session: Session, run: MatchRun) -> dict:
    pos = session.get(Position, run.position_id)
    project = session.get(Project, pos.project_id)
    results = session.exec(select(MatchResult).where(MatchResult.run_id == run.id).order_by(MatchResult.rank)).all()
    decisions = _decision_map(session, pos.id)
    runner = session.get(User, run.run_by)
    return {"id": run.id, "position_id": pos.id, "position_title": pos.title, "project_name": project.name,
            "created_at": run.created_at, "run_by": decrypt(runner.full_name_enc) if runner else "—",
            "weights": run.weights, "engine_version": run.engine_version, "evaluated": run.evaluated,
            "eligible": run.eligible, "results": [result_out(session, r, decisions) for r in results]}


def decision_out(session: Session, d: HRDecision) -> dict:
    prof = session.get(Profile, d.profile_id)
    user = session.get(User, prof.user_id) if prof else None
    by = session.get(User, d.decided_by)
    pos = session.get(Position, d.position_id)
    return {"id": d.id, "position_id": d.position_id, "position_title": pos.title if pos else "—",
            "profile_id": str(d.profile_id), "full_name": decrypt(user.full_name_enc) if user else "—",
            "decision": d.decision, "label": DECISION_LABELS[d.decision], "justification": d.justification,
            "score_at_decision": d.score_at_decision, "decided_by": decrypt(by.full_name_enc) if by else "—",
            "created_at": d.created_at}


def employee_opportunities(session: Session, prof: Profile) -> list[dict]:
    cand = candidate_from_profile(session, prof)
    out = []
    rows = session.exec(select(Position, Project).join(Project, Project.id == Position.project_id)
                        .where(Position.status == "open", Project.status.in_(("active", "planning")))).all()
    for pos, project in rows:
        spec = spec_from_position(session, pos)
        if not spec.requirements:
            continue
        res = evaluate(cand, spec)
        out.append({"position_id": pos.id, "title": pos.title, "project_name": project.name, "project_area": project.area,
                    "project_status": project.status, "seniority": pos.seniority, "openings": pos.openings,
                    "description": pos.description, **res})
    out.sort(key=lambda x: (not x["eligible"], -x["score"]))
    return out
