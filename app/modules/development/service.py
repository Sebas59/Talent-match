from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.crypto import decrypt
from app.core.time import utcnow
from app.modules.auth.models import User
from app.modules.development.models import LearningItem, LearningPath
from app.modules.development.recommender import recommend_for_gaps
from app.modules.profiles.models import Profile
from app.modules.projects.models import Position

CATALOG_NOTE = ("Cursos tomados de los datasets del proyecto (Coursera.csv, Udemy_Courses.xlsx). "
                "Disponibilidad y precio no verificados en línea.")


def build_items(gaps: list[dict], max_skills: int = 6) -> list[LearningItem]:
    items, order = [], 0
    for rec in recommend_for_gaps(gaps, max_items=max_skills):
        if rec["kind"] == "certification":
            continue
        courses = rec["courses"][:2] or [None]
        for c in courses:
            order += 1
            items.append(LearningItem(
                path_id=0, skill=rec["skill"][:120], skill_key=(rec["skill_key"] or rec["skill"])[:120],
                skill_kind=rec["kind"] if rec["kind"] in ("tech", "power") else "tech", order=order,
                course_title=c["course_title"] if c else None, platform=c["platform"] if c else "Interna",
                provider=c["provider"] if c else "Por definir con RR. HH.", url=c["url"] if c else None,
                rating=c["rating"] if c else None, hours=c["hours"] if c else None,
                hours_estimated=c["hours_estimated"] if c else False, level=c["level"] if c else None,
                relevance=c["relevance"] if c else None))
    return items


def create_path(session: Session, *, profile_id: uuid.UUID, title: str, gaps: list[dict], assigned_by: uuid.UUID | None,
                position_id: int | None = None, due_date: str | None = None, note: str | None = None,
                self_assigned: bool = False) -> LearningPath:
    items = build_items(gaps)
    if not items:
        raise HTTPException(status_code=422, detail="No hay brechas para construir la ruta")
    lp = LearningPath(profile_id=profile_id, title=title[:160], position_id=position_id, assigned_by=assigned_by,
                      self_assigned=self_assigned, due_date=due_date, note=note)
    session.add(lp)
    session.flush()
    for it in items:
        it.path_id = lp.id
        session.add(it)
    session.commit()
    session.refresh(lp)
    return lp


def path_items(session: Session, path_id: int) -> list[LearningItem]:
    return list(session.exec(select(LearningItem).where(LearningItem.path_id == path_id).order_by(LearningItem.order)))


def progress(items: list[LearningItem]) -> int:
    return round(sum(i.progress for i in items) / len(items)) if items else 0


def path_out(session: Session, lp: LearningPath, with_owner: bool = False) -> dict:
    items = path_items(session, lp.id)
    pos = session.get(Position, lp.position_id) if lp.position_id else None
    by = session.get(User, lp.assigned_by) if lp.assigned_by else None
    out = {
        "id": lp.id, "title": lp.title, "status": lp.status, "due_date": lp.due_date, "note": lp.note,
        "self_assigned": lp.self_assigned, "created_at": lp.created_at, "updated_at": lp.updated_at,
        "position": {"id": pos.id, "title": pos.title} if pos else None,
        "assigned_by": decrypt(by.full_name_enc) if by else None, "progress": progress(items),
        "target_skills": sorted({i.skill for i in items}),
        "total_hours": round(sum(i.hours or 0 for i in items), 1),
        "completed_items": sum(1 for i in items if i.status == "completed"), "total_items": len(items),
        "items": [i.model_dump() for i in items], "catalog_note": CATALOG_NOTE,
    }
    if with_owner:
        prof = session.get(Profile, lp.profile_id)
        user = session.get(User, prof.user_id) if prof else None
        out["profile_id"] = str(lp.profile_id)
        out["full_name"] = decrypt(user.full_name_enc) if user else "—"
        out["department"] = user.department if user else None
    return out


def own_item(session: Session, prof: Profile, item_id: int) -> tuple[LearningItem, LearningPath]:
    it = session.get(LearningItem, item_id)
    lp = session.get(LearningPath, it.path_id) if it else None
    if it is None or lp is None or lp.profile_id != prof.id:  # control de propiedad
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    return it, lp


def update_item(session: Session, it: LearningItem, lp: LearningPath, status: str | None, prog: int | None) -> None:
    if prog is not None:
        it.progress = max(0, min(100, prog))
        it.status = "completed" if it.progress == 100 else ("in_progress" if it.progress > 0 else "pending")
    if status:
        it.status = status
        it.progress = 100 if status == "completed" else (max(it.progress, 10) if status == "in_progress" else 0)
    it.completed_at = utcnow() if it.status == "completed" else None
    session.add(it)
    items = path_items(session, lp.id)
    lp.status = "completed" if items and all(i.status == "completed" for i in items) else "active"
    lp.updated_at = utcnow()
    session.add(lp)
    session.commit()


def paths_for(session: Session, profile_id: uuid.UUID) -> list[LearningPath]:
    return list(session.exec(select(LearningPath).where(LearningPath.profile_id == profile_id,
                                                        LearningPath.status != "archived")
                             .order_by(col(LearningPath.created_at).desc())))
