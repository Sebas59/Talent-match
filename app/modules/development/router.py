import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.core.database import SessionDep
from app.modules.audit.service import log_event
from app.modules.auth.deps import HR, Employee
from app.modules.development import service
from app.modules.development.models import LearningPath
from app.modules.development.recommender import recommend_for_gaps
from app.modules.matching import service as matching
from app.modules.matching.models import MatchResult
from app.modules.profiles import service as profiles
from app.modules.projects import service as projects

router = APIRouter(prefix="/development", tags=["desarrollo"])


class GapIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="tech", pattern="^(tech|power|certification)$")
    key: str | None = Field(default=None, max_length=120)
    importance: str | None = None


class PathCreate(BaseModel):
    profile_id: uuid.UUID
    title: str = Field(min_length=3, max_length=160)
    position_id: int | None = None
    match_result_id: int | None = None
    gaps: list[GapIn] = Field(default_factory=list, max_length=12)
    due_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str | None = Field(default=None, max_length=400)


class SelfPathCreate(BaseModel):
    position_id: int


class ItemPatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|in_progress|completed)$")
    progress: int | None = Field(default=None, ge=0, le=100)


# ------------------------------ Empleado ------------------------------
@router.get("/me")
def my_paths(session: SessionDep, user: Employee):
    prof = profiles.get_or_create(session, user)
    return [service.path_out(session, lp) for lp in service.paths_for(session, prof.id)]


@router.get("/me/recommendations")
def my_recommendations(session: SessionDep, user: Employee, position_id: int | None = None):
    prof = profiles.get_or_create(session, user)
    opps = matching.employee_opportunities(session, prof)
    if position_id is not None:
        opps = [o for o in opps if o["position_id"] == position_id]
    if not opps:
        return {"position": None, "recommendations": [], "catalog_note": service.CATALOG_NOTE}
    best = opps[0]
    return {"position": {"id": best["position_id"], "title": best["title"], "project_name": best["project_name"],
                         "score": best["score"]},
            "recommendations": recommend_for_gaps(best["gaps"], max_items=6), "catalog_note": service.CATALOG_NOTE}


@router.post("/me/paths", status_code=201)
def self_assign(body: SelfPathCreate, request: Request, session: SessionDep, user: Employee):
    prof = profiles.get_or_create(session, user)
    opp = next((o for o in matching.employee_opportunities(session, prof) if o["position_id"] == body.position_id), None)
    if opp is None:
        raise HTTPException(status_code=404, detail="Oportunidad no disponible")
    lp = service.create_path(session, profile_id=prof.id, title=f"Ruta hacia {opp['title']}", gaps=opp["gaps"],
                             assigned_by=None, position_id=body.position_id, self_assigned=True)
    log_event(session, actor=user.id, actor_role=user.role, action="path_self_assigned", resource="learning_path",
              resource_id=str(lp.id), request=request, category="development")
    return service.path_out(session, lp)


@router.patch("/items/{item_id}")
def update_item(item_id: int, body: ItemPatch, request: Request, session: SessionDep, user: Employee):
    prof = profiles.get_or_create(session, user)
    it, lp = service.own_item(session, prof, item_id)
    service.update_item(session, it, lp, body.status, body.progress)
    log_event(session, actor=user.id, actor_role=user.role, action="learning_progress", resource="learning_item",
              resource_id=str(it.id), request=request, category="development", detail=f"progreso={it.progress}")
    return service.path_out(session, lp)


# ------------------------------ RR. HH. ------------------------------
@router.post("/paths", status_code=201)
def assign_path(body: PathCreate, request: Request, session: SessionDep, user: HR):
    prof, _ = profiles.get_published(session, body.profile_id)
    gaps = [g.model_dump() for g in body.gaps]
    if body.match_result_id:
        mr = session.get(MatchResult, body.match_result_id)
        if mr is None or mr.profile_id != prof.id:
            raise HTTPException(status_code=422, detail="Resultado de matching no válido para este perfil")
        gaps = gaps or mr.details.get("gaps", [])
    elif not gaps and body.position_id:
        pos = projects.get_position(session, body.position_id)
        from app.modules.matching.engine import evaluate

        res = evaluate(matching.candidate_from_profile(session, prof), matching.spec_from_position(session, pos))
        gaps = res["gaps"]
    lp = service.create_path(session, profile_id=prof.id, title=body.title, gaps=gaps, assigned_by=user.id,
                             position_id=body.position_id, due_date=body.due_date, note=body.note)
    log_event(session, actor=user.id, actor_role=user.role, action="path_assigned", resource="learning_path",
              resource_id=str(lp.id), request=request, category="development")
    return service.path_out(session, lp, with_owner=True)


@router.get("/paths")
def list_paths(session: SessionDep, _: HR, profile_id: uuid.UUID | None = None):
    q = select(LearningPath).where(LearningPath.status != "archived").order_by(col(LearningPath.updated_at).desc())
    if profile_id:
        q = q.where(LearningPath.profile_id == profile_id)
    return [service.path_out(session, lp, with_owner=True) for lp in session.exec(q).all()]


@router.post("/paths/{path_id}/archive")
def archive(path_id: int, request: Request, session: SessionDep, user: HR):
    lp = session.get(LearningPath, path_id)
    if lp is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    lp.status = "archived"
    session.add(lp)
    session.commit()
    log_event(session, actor=user.id, actor_role=user.role, action="path_archived", resource="learning_path",
              resource_id=str(lp.id), request=request, category="development")
    return {"ok": True}


@router.post("/recommend")
def recommend(gaps: list[GapIn], _: HR):
    return {"recommendations": recommend_for_gaps([g.model_dump() for g in gaps], max_items=8),
            "catalog_note": service.CATALOG_NOTE}
