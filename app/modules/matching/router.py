import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.core.database import SessionDep
from app.modules.audit.service import log_event
from app.modules.auth.deps import HR, Employee
from app.modules.matching import service
from app.modules.matching.models import DECISION_LABELS, HRDecision, MatchResult, MatchRun
from app.modules.profiles import service as profiles
from app.modules.projects import service as projects
from app.modules.projects.models import Position
from app.modules.projects.schemas import WeightsIn

router = APIRouter(tags=["matching"])


class MatchRequest(BaseModel):
    weights: WeightsIn | None = None   # si se omite se usan las del cargo


class DecisionIn(BaseModel):
    profile_id: uuid.UUID
    decision: str = Field(pattern="^(shortlisted|interview|selected|on_hold|not_selected)$")
    justification: str = Field(min_length=20, max_length=1000)
    match_result_id: int | None = None


@router.post("/positions/{position_id}/match")
def run_match(position_id: int, body: MatchRequest, request: Request, session: SessionDep, user: HR):
    pos = projects.get_position(session, position_id)
    run = service.run_match(session, pos, user, body.weights.model_dump() if body.weights else None)
    log_event(session, actor=user.id, actor_role=user.role, action="match_run", resource="position",
              resource_id=str(pos.id), request=request, category="matching",
              detail=f"evaluados={run.evaluated}; elegibles={run.eligible}")
    return service.run_out(session, run)


@router.get("/positions/{position_id}/runs")
def list_runs(position_id: int, session: SessionDep, _: HR):
    projects.get_position(session, position_id)
    runs = session.exec(select(MatchRun).where(MatchRun.position_id == position_id)
                        .order_by(col(MatchRun.id).desc()).limit(20)).all()
    return [{"id": r.id, "created_at": r.created_at, "evaluated": r.evaluated, "eligible": r.eligible,
             "weights": r.weights} for r in runs]


@router.get("/positions/{position_id}/latest-run")
def latest(position_id: int, session: SessionDep, _: HR):
    projects.get_position(session, position_id)
    run = service.latest_run(session, position_id)
    return service.run_out(session, run) if run else None


@router.get("/match-runs/{run_id}")
def get_run(run_id: int, session: SessionDep, _: HR):
    run = session.get(MatchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return service.run_out(session, run)


@router.get("/match-results/{result_id}")
def get_result(result_id: int, request: Request, session: SessionDep, user: HR):
    r = session.get(MatchResult, result_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    run = session.get(MatchRun, r.run_id)
    out = service.result_out(session, r, service._decision_map(session, run.position_id))
    log_event(session, actor=user.id, actor_role=user.role, action="match_result_view", resource="match_result",
              resource_id=str(r.id), request=request, category="matching")
    return out


@router.post("/positions/{position_id}/decisions", status_code=201)
def record_decision(position_id: int, body: DecisionIn, request: Request, session: SessionDep, user: HR):
    pos = projects.get_position(session, position_id)
    profiles.get_published(session, body.profile_id)  # solo sobre perfiles publicados y autorizados
    score = None
    if body.match_result_id:
        mr = session.get(MatchResult, body.match_result_id)
        run = session.get(MatchRun, mr.run_id) if mr else None
        if mr is None or run is None or run.position_id != pos.id or mr.profile_id != body.profile_id:
            raise HTTPException(status_code=422, detail="El resultado no corresponde al cargo y perfil indicados")
        score = mr.score
    d = HRDecision(position_id=pos.id, profile_id=body.profile_id, match_result_id=body.match_result_id,
                   decision=body.decision, justification=body.justification.strip(), score_at_decision=score,
                   decided_by=user.id)
    session.add(d)
    session.commit()
    session.refresh(d)
    log_event(session, actor=user.id, actor_role=user.role, action="hr_decision", resource="position",
              resource_id=str(pos.id), request=request, category="matching", detail=f"decision={body.decision}")
    return service.decision_out(session, d)


@router.get("/positions/{position_id}/decisions")
def position_decisions(position_id: int, session: SessionDep, _: HR):
    rows = session.exec(select(HRDecision).where(HRDecision.position_id == position_id)
                        .order_by(col(HRDecision.created_at).desc())).all()
    return [service.decision_out(session, d) for d in rows]


@router.get("/decisions")
def recent_decisions(session: SessionDep, _: HR, limit: int = 30):
    rows = session.exec(select(HRDecision).order_by(col(HRDecision.created_at).desc()).limit(min(limit, 100))).all()
    return [service.decision_out(session, d) for d in rows]


# ---------------------------------------------------------------------------
# Vista del empleado: solo su propia compatibilidad
# ---------------------------------------------------------------------------
@router.get("/opportunities")
def my_opportunities(session: SessionDep, user: Employee):
    prof = profiles.get_or_create(session, user)
    items = service.employee_opportunities(session, prof)
    return {"profile_status": prof.status,
            "confirmed_skills": len(profiles.skills_of(session, prof.id, confirmed_only=True)), "items": items}


@router.get("/opportunities/processes")
def my_processes(session: SessionDep, user: Employee):
    """Transparencia: el empleado ve las decisiones registradas sobre su perfil (sin el nombre de quien decidió)."""
    prof = profiles.get_or_create(session, user)
    rows = session.exec(select(HRDecision, Position).join(Position, Position.id == HRDecision.position_id)
                        .where(HRDecision.profile_id == prof.id).order_by(col(HRDecision.created_at).desc())).all()
    return [{"position_id": p.id, "position_title": p.title, "decision": d.decision,
             "label": DECISION_LABELS[d.decision], "justification": d.justification, "created_at": d.created_at}
            for d, p in rows]


@router.get("/opportunities/{position_id}")
def my_opportunity(position_id: int, session: SessionDep, user: Employee):
    pos = session.get(Position, position_id)
    if pos is None or pos.status != "open":
        raise HTTPException(status_code=404, detail="Oportunidad no disponible")
    prof = profiles.get_or_create(session, user)
    match = next((o for o in service.employee_opportunities(session, prof) if o["position_id"] == position_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Oportunidad no disponible")
    from app.modules.development.recommender import recommend_for_gaps

    match["recommendations"] = recommend_for_gaps(match["gaps"])
    return match
