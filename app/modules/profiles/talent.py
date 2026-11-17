"""Directorio de talento para RR. HH.: solo perfiles publicados con autorización vigente."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlmodel import func, select

from app.core.crypto import decrypt
from app.core.database import SessionDep
from app.core.text import norm
from app.modules.audit.service import log_event
from app.modules.auth.deps import HR
from app.modules.development.models import LearningPath
from app.modules.profiles import service
from app.modules.profiles.schemas import ProfileOut, TalentCard

router = APIRouter(prefix="/talent", tags=["talento"])


def _active_paths(session, profile_id) -> int:
    return session.exec(select(func.count()).select_from(LearningPath)
                        .where(LearningPath.profile_id == profile_id, LearningPath.status == "active")).one()


@router.get("", response_model=list[TalentCard])
def directory(session: SessionDep, _: HR,
              q: Annotated[str, Query(max_length=60)] = "",
              skill: Annotated[str, Query(max_length=60)] = "",
              department: Annotated[str, Query(max_length=80)] = "",
              min_years: Annotated[float, Query(ge=0, le=60)] = 0,
              mobility: bool | None = None):
    nq, ns = norm(q), norm(skill)
    out = []
    for prof, user in service.published_profiles(session):
        if department and (user.department or "") != department:
            continue
        if prof.years_experience < min_years:
            continue
        if mobility is not None and prof.open_to_mobility != mobility:
            continue
        skills = service.skills_of(session, prof.id, confirmed_only=True)
        if ns and not any(ns in norm(s.name) or ns == s.key for s in skills):
            continue
        if nq:
            hay = " ".join([decrypt(user.full_name_enc) or "", prof.headline or "", user.job_title or ""]
                           + [s.name for s in skills])
            if nq not in norm(hay):
                continue
        out.append(service.talent_card(session, prof, user, _active_paths(session, prof.id)))
    out.sort(key=lambda c: (-c.completeness, c.full_name))
    return out


@router.get("/facets")
def facets(session: SessionDep, _: HR):
    deps, skills = set(), {}
    for prof, user in service.published_profiles(session):
        if user.department:
            deps.add(user.department)
        for s in service.skills_of(session, prof.id, confirmed_only=True):
            skills[s.name] = skills.get(s.name, 0) + 1
    return {"departments": sorted(deps),
            "skills": [k for k, _ in sorted(skills.items(), key=lambda kv: -kv[1])[:40]]}


@router.get("/{profile_id}", response_model=ProfileOut)
def talent_profile(profile_id: uuid.UUID, request: Request, session: SessionDep, user: HR):
    prof, owner = service.get_published(session, profile_id)
    log_event(session, actor=user.id, actor_role=user.role, action="profile_view", resource="profile",
              resource_id=str(prof.id), request=request, category="data")
    return service.published_view(session, prof, owner)
