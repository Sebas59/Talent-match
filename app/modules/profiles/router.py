"""Autoservicio del empleado: su perfil, su CV, sus confirmaciones y su publicación.

Todas las rutas usan el usuario autenticado como dueño: no existe parámetro que permita
operar sobre el perfil de otra persona (control de propiedad por diseño).
"""
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import col, select

from app.core.config import get_settings
from app.core.database import SessionDep
from app.core.time import utcnow
from app.modules.admin.settings import get_setting
from app.modules.audit.service import log_event
from app.modules.consent import service as consent_service
from app.modules.extraction.service import InvalidDocument, run_extraction
from app.modules.profiles import service
from app.modules.profiles.models import ExtractionRun
from app.modules.profiles.schemas import (BulkConfirm, EntryCreate, EntryPatch, ExtractionOut, ProfileOut,
                                          ProfileUpdate, SkillCreate, SkillPatch)
from app.modules.auth.deps import Employee

router = APIRouter(prefix="/profiles/me", tags=["mi perfil"])


def _audit(session, user, action, request, detail=None, resource="profile"):
    log_event(session, actor=user.id, actor_role=user.role, action=action, resource=resource,
              request=request, category="data", detail=detail)


@router.get("", response_model=ProfileOut)
def my_profile(session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    return service.owner_view(session, prof, user)


@router.patch("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    data = body.model_dump(exclude_unset=True)
    if "years_experience" in data:
        prof.years_experience, prof.years_source = data.pop("years_experience"), "manual"
    if "education_level" in data:
        prof.education_level, prof.education_source = data.pop("education_level"), "manual"
    if "visibility" in data:
        allowed = {"summary", "experience", "education", "certification", "language"}
        prof.visibility = {**prof.visibility, **{k: bool(v) for k, v in data.pop("visibility").items() if k in allowed}}
    for k, v in data.items():
        setattr(prof, k, v)
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "profile_update", request)
    return service.owner_view(session, prof, user)


@router.post("/cv", response_model=ProfileOut, status_code=201)
def upload_cv(request: Request, session: SessionDep, user: Employee,
              file: Annotated[UploadFile, File(description="Hoja de vida en PDF, JSON, PNG o JPG")]):
    consent = consent_service.current(session, user.id)
    if not consent or not consent.processing:
        raise HTTPException(status_code=403, detail="Primero debe otorgar la autorización de tratamiento de datos")
    s = get_settings()
    max_bytes = s.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)  # nunca leer más del límite
    allow_external = bool(consent.external_ai and get_setting(session, "external_ai_allowed"))
    try:
        out = run_extraction(file.filename or "", data, allow_external=allow_external,
                             preferred_provider=str(get_setting(session, "preferred_provider") or "auto"))
    except InvalidDocument as exc:
        log_event(session, actor=user.id, actor_role=user.role, action="cv_rejected", resource="profile",
                  request=request, category="security", detail=f"status={exc.status}")
        raise HTTPException(status_code=exc.status, detail=str(exc))
    finally:
        del data  # procesamiento en memoria: el archivo no se guarda
    prof = service.get_or_create(session, user)
    run = service.apply_extraction(session, prof, out)
    session.commit()
    _audit(session, user, "cv_processed", request, resource="extraction",
           detail=f"tipo={out.source_type}; proveedor={out.provider}; externo={out.external_used}; "
                  f"sensibles_descartados={len(out.sensitive)}")
    session.refresh(run)
    return service.owner_view(session, prof, user)


@router.get("/extractions", response_model=list[ExtractionOut])
def my_extractions(session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    rows = session.exec(select(ExtractionRun).where(ExtractionRun.profile_id == prof.id)
                        .order_by(col(ExtractionRun.id).desc())).all()
    return [service.extraction_out(r) for r in rows]


@router.post("/skills", response_model=ProfileOut, status_code=201)
def add_skill(body: SkillCreate, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    new = service.make_skill(prof, body.kind, body.name, body.level)
    dup = next((s for s in service.skills_of(session, prof.id) if s.kind == new.kind and s.key == new.key), None)
    if dup:
        dup.status, dup.confirmed_at = "confirmed", utcnow()
        dup.level = body.level or dup.level
        session.add(dup)
    else:
        session.add(new)
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "skill_added", request)
    return service.owner_view(session, prof, user)


@router.patch("/skills/{skill_id}", response_model=ProfileOut)
def patch_skill(skill_id: int, body: SkillPatch, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    s = service.own_skill(session, prof, skill_id)
    if body.name and body.name.strip() != s.name:
        repl = service.make_skill(prof, s.kind, body.name, s.level)
        s.key, s.name = repl.key, repl.name
    if body.level is not None:
        s.level = body.level
    if body.status:
        s.status = body.status
        s.confirmed_at = utcnow() if body.status == "confirmed" else None
    session.add(s)
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "skill_review", request, detail=f"estado={s.status}")
    return service.owner_view(session, prof, user)


@router.delete("/skills/{skill_id}", response_model=ProfileOut)
def delete_skill(skill_id: int, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    session.delete(service.own_skill(session, prof, skill_id))
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "skill_deleted", request)
    return service.owner_view(session, prof, user)


@router.post("/confirm-all", response_model=ProfileOut)
def confirm_all(body: BulkConfirm, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    n = 0
    for s in service.skills_of(session, prof.id):
        if s.status == "pending" and (body.kind is None or s.kind == body.kind) \
                and (s.confidence or 1.0) >= body.min_confidence:
            s.status, s.confirmed_at = "confirmed", utcnow()
            session.add(s)
            n += 1
    if body.include_entries:
        for e in service.entries_of(session, prof.id):
            if e.status == "pending":
                e.status = "confirmed"
                session.add(e)
                n += 1
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "bulk_confirm", request, detail=f"elementos={n}")
    return service.owner_view(session, prof, user)


@router.post("/entries", response_model=ProfileOut, status_code=201)
def add_entry(body: EntryCreate, request: Request, session: SessionDep, user: Employee):
    from app.modules.profiles.models import ProfileEntry

    prof = service.get_or_create(session, user)
    session.add(ProfileEntry(profile_id=prof.id, kind=body.kind, title=body.title, organization=body.organization,
                             start=body.start, end=None if body.current else body.end, current=body.current,
                             years=service.entry_years(body.start, body.end, body.current), level=body.level,
                             origin="manual", status="confirmed"))
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "entry_added", request, detail=f"tipo={body.kind}")
    return service.owner_view(session, prof, user)


@router.patch("/entries/{entry_id}", response_model=ProfileOut)
def patch_entry(entry_id: int, body: EntryPatch, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    e = service.own_entry(session, prof, entry_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    if e.kind == "experience":
        e.years = service.entry_years(e.start, e.end, e.current) or e.years
    session.add(e)
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "entry_review", request, detail=f"estado={e.status}")
    return service.owner_view(session, prof, user)


@router.delete("/entries/{entry_id}", response_model=ProfileOut)
def delete_entry(entry_id: int, request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    session.delete(service.own_entry(session, prof, entry_id))
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "entry_deleted", request)
    return service.owner_view(session, prof, user)


@router.post("/publish", response_model=ProfileOut)
def publish(request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    blockers = service.publish_blockers(session, prof, service.skills_of(session, prof.id))
    if blockers:
        raise HTTPException(status_code=409, detail=" ".join(blockers))
    prof.status, prof.published_at = "published", utcnow()
    service.touch(session, prof)
    session.commit()
    _audit(session, user, "profile_published", request)
    return service.owner_view(session, prof, user)


@router.post("/unpublish", response_model=ProfileOut)
def unpublish(request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    service.unpublish(session, prof)
    session.commit()
    _audit(session, user, "profile_unpublished", request)
    return service.owner_view(session, prof, user)


@router.get("/export")
def export(request: Request, session: SessionDep, user: Employee):
    prof = service.get_or_create(session, user)
    _audit(session, user, "data_export", request, resource="privacy")
    return JSONResponse(service.export_all(session, prof, user),
                        headers={"Content-Disposition": 'attachment; filename="mis-datos-talent-match.json"'})


@router.delete("/data", response_model=ProfileOut)
def wipe(request: Request, session: SessionDep, user: Employee):
    """Supresión inmediata del contenido del perfil por el titular (la cuenta se conserva)."""
    prof = service.get_or_create(session, user)
    service.wipe_profile_data(session, prof)
    session.commit()
    _audit(session, user, "profile_data_wiped", request, resource="privacy")
    return service.owner_view(session, prof, user)
