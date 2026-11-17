"""Analítica organizacional calculada SIEMPRE desde la base de datos (sin cifras decorativas).

Oferta  = competencias confirmadas en perfiles publicados.
Demanda = requisitos de cargos abiertos.
Brecha  = demanda sin oferta suficiente.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from sqlmodel import Session, col, func, select

from app.modules.admin.settings import get_setting
from app.modules.auth.models import User
from app.modules.development.models import LearningItem, LearningPath
from app.modules.matching.models import HRDecision, MatchResult, MatchRun
from app.modules.profiles import service as profiles
from app.modules.profiles.models import Profile, ProfileSkill
from app.modules.projects.models import Position, PositionRequirement, Project


def _count(session: Session, model, *where) -> int:
    q = select(func.count()).select_from(model)
    for w in where:
        q = q.where(w)
    return session.exec(q).one()


def supply(session: Session, department: str | None = None, kind: str | None = None) -> tuple[Counter, dict, int]:
    pool = profiles.published_profiles(session)
    if department:
        pool = [(p, u) for p, u in pool if u.department == department]
    c: Counter = Counter()
    meta: dict = {}
    for prof, _ in pool:
        for s in profiles.skills_of(session, prof.id, confirmed_only=True):
            if kind and s.kind != kind:
                continue
            c[s.key] += 1
            meta.setdefault(s.key, {"name": s.name, "kind": s.kind})
    return c, meta, len(pool)


def demand(session: Session, project_id: int | None = None, kind: str | None = None) -> tuple[Counter, dict, Counter]:
    q = (select(PositionRequirement, Position).join(Position, Position.id == PositionRequirement.position_id)
         .where(Position.status == "open"))
    if project_id:
        q = q.where(Position.project_id == project_id)
    c: Counter = Counter()
    mand: Counter = Counter()
    meta: dict = {}
    for r, _p in session.exec(q).all():
        if r.kind == "certification" or (kind and r.kind != kind):
            continue
        c[r.key] += 1
        if r.importance == "mandatory":
            mand[r.key] += 1
        meta.setdefault(r.key, {"name": r.name, "kind": r.kind})
    return c, meta, mand


def skills_report(session: Session, department: str | None = None, kind: str | None = None,
                  project_id: int | None = None) -> dict:
    sup, smeta, n_prof = supply(session, department, kind)
    dem, dmeta, mand = demand(session, project_id, kind)
    meta = {**dmeta, **smeta}
    top = [{"key": k, "name": meta[k]["name"], "kind": meta[k]["kind"], "profiles": n,
            "share": round(n / n_prof * 100, 1) if n_prof else 0} for k, n in sup.most_common(15)]
    gaps = []
    for k, d in dem.items():
        s = sup.get(k, 0)
        gaps.append({"key": k, "name": meta[k]["name"], "kind": meta[k]["kind"], "demand": d, "supply": s,
                     "mandatory_in": mand.get(k, 0), "gap": d - s,
                     "status": "crítica" if s == 0 else ("escasa" if s < d else "cubierta")})
    gaps.sort(key=lambda g: (g["supply"] > 0, -(g["demand"] - g["supply"]), -g["mandatory_in"]))
    scarce = [g for g in gaps if g["status"] != "cubierta"][:15]
    by_kind = Counter(meta[k]["kind"] for k in sup)
    return {"profiles": n_prof, "distinct_skills": len(sup), "by_kind": dict(by_kind), "top": top,
            "gaps": gaps[:25], "scarce": scarce,
            "coverage_pct": round(sum(1 for g in gaps if g["supply"] > 0) / len(gaps) * 100, 1) if gaps else 0.0}


def positions_report(session: Session, project_id: int | None = None) -> list[dict]:
    threshold = float(get_setting(session, "availability_threshold") or 70)
    q = select(Position, Project).join(Project, Project.id == Position.project_id).where(Position.status == "open")
    if project_id:
        q = q.where(Project.id == project_id)
    out = []
    for pos, proj in session.exec(q).all():
        run = session.exec(select(MatchRun).where(MatchRun.position_id == pos.id)
                           .order_by(col(MatchRun.id).desc())).first()
        results = session.exec(select(MatchResult).where(MatchResult.run_id == run.id)).all() if run else []
        scores = [r.score for r in results]
        out.append({"position_id": pos.id, "title": pos.title, "project": proj.name, "project_id": proj.id,
                    "openings": pos.openings, "has_run": run is not None,
                    "run_at": run.created_at.isoformat() if run else None,
                    "evaluated": len(results), "eligible": sum(1 for r in results if r.eligible),
                    "available": sum(1 for r in results if r.eligible and r.score >= threshold),
                    "best_score": max(scores) if scores else None,
                    "avg_score": round(mean(scores), 1) if scores else None,
                    "decisions": _count(session, HRDecision, HRDecision.position_id == pos.id)})
    out.sort(key=lambda x: (x["available"], -(x["openings"])))
    return out


def training_report(session: Session) -> dict:
    paths = session.exec(select(LearningPath).where(LearningPath.status != "archived")).all()
    items = session.exec(select(LearningItem).join(LearningPath, LearningPath.id == LearningItem.path_id)
                         .where(LearningPath.status != "archived")).all()
    by_skill: dict = defaultdict(lambda: {"items": 0, "completed": 0})
    for it in items:
        by_skill[it.skill]["items"] += 1
        by_skill[it.skill]["completed"] += it.status == "completed"
    needs: Counter = Counter()
    names = {}
    # Necesidades: brechas en la última ejecución de cada cargo abierto (perfiles elegibles o cercanos)
    for pos in session.exec(select(Position).where(Position.status == "open")).all():
        run = session.exec(select(MatchRun).where(MatchRun.position_id == pos.id)
                           .order_by(col(MatchRun.id).desc())).first()
        if not run:
            continue
        for r in session.exec(select(MatchResult).where(MatchResult.run_id == run.id, MatchResult.rank <= 5)).all():
            for g in r.details.get("gaps", []):
                if g.get("kind") != "certification":
                    needs[g["key"]] += 1
                    names[g["key"]] = g["name"]
    prog = [round(sum(i.progress for i in items if i.path_id == p.id) /
                  max(1, sum(1 for i in items if i.path_id == p.id))) for p in paths]
    return {"paths": len(paths), "active": sum(1 for p in paths if p.status == "active"),
            "completed": sum(1 for p in paths if p.status == "completed"),
            "items": len(items), "items_completed": sum(1 for i in items if i.status == "completed"),
            "avg_progress": round(mean(prog), 1) if prog else 0.0,
            "needs": [{"key": k, "name": names[k], "count": n} for k, n in needs.most_common(12)],
            "by_skill": sorted([{"skill": k, **v} for k, v in by_skill.items()], key=lambda x: -x["items"])[:12]}


def departments(session: Session) -> list[str]:
    rows = session.exec(select(User.department).where(User.role == "employee", User.department != None).distinct()).all()  # noqa: E711
    return sorted(r for r in rows if r)


def hr_overview(session: Session) -> dict:
    employees = _count(session, User, User.role == "employee", User.is_active == True)  # noqa: E712
    published = len(profiles.published_profiles(session))
    confirmed = session.exec(select(func.count(func.distinct(ProfileSkill.key)))
                             .where(ProfileSkill.status == "confirmed")).one()
    active_projects = _count(session, Project, Project.status == "active")
    open_positions = _count(session, Position, Position.status == "open")
    runs = _count(session, MatchRun)
    decisions = _count(session, HRDecision)
    pos = positions_report(session)
    mobility = sum(p["available"] for p in pos)
    sk = skills_report(session)
    return {"employees": employees, "published_profiles": published,
            "draft_profiles": _count(session, Profile, Profile.status == "draft"),
            "distinct_confirmed_skills": confirmed, "active_projects": active_projects,
            "open_positions": open_positions, "match_runs": runs, "decisions": decisions,
            "mobility_opportunities": mobility, "critical_gaps": sum(1 for g in sk["gaps"] if g["status"] == "crítica"),
            "coverage_pct": sk["coverage_pct"]}
