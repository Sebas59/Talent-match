"""Un dashboard distinto por rol. Todos los indicadores salen de la base de datos."""
from datetime import timedelta

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.core.database import SessionDep
from app.core.time import utcnow
from app.modules.analytics import service as analytics
from app.modules.audit.models import AuditLog
from app.modules.auth.deps import CurrentUser
from app.modules.auth.service import display_name
from app.modules.auth.models import AuthSession, Invitation, User
from app.modules.matching.models import HRDecision
from app.modules.privacy.models import PrivacyRequest

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Acciones que se muestran como "actividad reciente" a RR. HH. (sin datos personales)
HR_FEED = ("match_run", "hr_decision", "position_created", "project_created", "path_assigned", "profile_published",
           "invitation_created", "invitation_accepted")


def _count(session, model, *where) -> int:
    q = select(func.count()).select_from(model)
    for w in where:
        q = q.where(w)
    return session.exec(q).one()


def employee_dashboard(session, user) -> dict:
    from app.modules.development import service as dev
    from app.modules.matching import service as matching
    from app.modules.profiles import service as profiles

    prof = profiles.get_or_create(session, user)
    view = profiles.owner_view(session, prof, user)
    opps = matching.employee_opportunities(session, prof)
    paths = [dev.path_out(session, lp) for lp in dev.paths_for(session, prof.id)]
    confirmed = [s for s in view.skills if s.status == "confirmed"]
    pending = sum(1 for s in view.skills if s.status == "pending") + sum(1 for e in view.entries if e.status == "pending")
    top_gaps = {}
    for o in opps[:3]:
        for g in o["gaps"][:4]:
            top_gaps.setdefault(g["name"], {"name": g["name"], "kind": g["kind"], "positions": 0})
            top_gaps[g["name"]]["positions"] += 1
    processes = _count(session, HRDecision, HRDecision.profile_id == prof.id)
    return {
        "role": "employee", "profile_status": prof.status, "completeness": view.completeness,
        "completeness_breakdown": view.completeness_breakdown, "consent": view.consent,
        "confirmed_tech": sum(1 for s in confirmed if s.kind == "tech"),
        "confirmed_power": sum(1 for s in confirmed if s.kind == "power"), "pending_review": pending,
        "has_cv": view.last_extraction is not None, "can_publish": view.can_publish,
        "publish_blockers": view.publish_blockers,
        "opportunities": [{"position_id": o["position_id"], "title": o["title"], "project_name": o["project_name"],
                           "score": o["score"], "eligible": o["eligible"], "missing": o["missing"][:3]} for o in opps[:4]],
        "opportunities_total": len(opps), "opportunities_70": sum(1 for o in opps if o["score"] >= 70 and o["eligible"]),
        "top_gaps": sorted(top_gaps.values(), key=lambda g: -g["positions"])[:6],
        "paths": [{"id": p["id"], "title": p["title"], "progress": p["progress"], "total_items": p["total_items"],
                   "completed_items": p["completed_items"], "due_date": p["due_date"]} for p in paths],
        "processes": processes,
    }


def hr_dashboard(session, user) -> dict:
    ov = analytics.hr_overview(session)
    sk = analytics.skills_report(session)
    pos = analytics.positions_report(session)
    tr = analytics.training_report(session)
    feed = session.exec(select(AuditLog).where(col(AuditLog.action).in_(HR_FEED))
                        .order_by(col(AuditLog.id).desc()).limit(10)).all()
    actors = {}
    activity = []
    for a in feed:
        if a.actor_id and a.actor_id not in actors:
            u = session.get(User, a.actor_id)
            actors[a.actor_id] = display_name(u)
        activity.append({"id": a.id, "ts": a.ts, "action": a.action, "actor": actors.get(a.actor_id, "Sistema"),
                         "actor_role": a.actor_role, "resource": a.resource, "detail": a.detail})
    return {"role": "hr", **ov, "top_skills": sk["top"][:8], "gaps": sk["scarce"][:8],
            "by_kind": sk["by_kind"], "positions": pos[:8], "training": tr, "activity": activity,
            "pending_invitations": _count(session, Invitation, Invitation.accepted_at == None,  # noqa: E711
                                          Invitation.revoked_at == None, Invitation.expires_at > utcnow())}  # noqa: E711


def admin_dashboard(session, user) -> dict:
    from app.modules.admin.router import system_status
    from app.modules.admin.settings import all_settings

    since = utcnow() - timedelta(days=7)
    by_role = {r: _count(session, User, User.role == r) for r in ("employee", "hr", "admin")}
    sec = session.exec(select(AuditLog).where(AuditLog.category == "security").order_by(col(AuditLog.id).desc())
                       .limit(8)).all()
    per_day = {}
    for a in session.exec(select(AuditLog).where(AuditLog.ts >= since)).all():
        d = a.ts.date().isoformat()
        per_day.setdefault(d, {"date": d, "total": 0, "security": 0})
        per_day[d]["total"] += 1
        per_day[d]["security"] += a.category == "security"
    return {
        "role": "admin", "users_by_role": by_role, "users_total": sum(by_role.values()),
        "inactive_users": _count(session, User, User.is_active == False),  # noqa: E712
        "active_sessions": _count(session, AuthSession, AuthSession.revoked_at == None,  # noqa: E711
                                  AuthSession.expires_at > utcnow()),
        "audit_events_7d": sum(d["total"] for d in per_day.values()),
        "security_events_7d": sum(d["security"] for d in per_day.values()),
        "activity_by_day": sorted(per_day.values(), key=lambda d: d["date"]),
        "security_recent": [{"id": a.id, "ts": a.ts, "action": a.action, "resource": a.resource, "detail": a.detail}
                            for a in sec],
        "privacy_open": _count(session, PrivacyRequest, col(PrivacyRequest.status).in_(("open", "in_progress"))),
        "privacy_total": _count(session, PrivacyRequest),
        "system": system_status(session), "settings": all_settings(session),
    }


@router.get("")
def dashboard(session: SessionDep, user: CurrentUser):
    if user.role == "employee":
        return employee_dashboard(session, user)
    if user.role == "hr":
        return hr_dashboard(session, user)
    return admin_dashboard(session, user)
