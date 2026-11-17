"""Lógica del perfil profesional: propiedad, fusión de extracciones, confirmación y publicación."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.crypto import decrypt
from app.core.text import clean_display, norm
from app.core.time import utcnow
from app.modules.admin.settings import get_setting
from app.modules.auth.models import User
from app.modules.catalog.skills import EDU_LEVELS, canonical_soft, canonical_tech, display_tech, soft_label
from app.modules.consent import service as consent_service
from app.modules.extraction.service import ExtractionOutput
from app.modules.profiles.models import ExtractionRun, Profile, ProfileEntry, ProfileSkill
from app.modules.profiles.schemas import EntryOut, ExtractionOut, ProfileOut, SkillOut, TalentCard

SECTION_KINDS = ("experience", "education", "certification", "language")


def confidence_label(c: float | None) -> str | None:
    if c is None:
        return None
    return "Alta" if c >= 0.85 else ("Media" if c >= 0.7 else "Baja")


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------
def get_or_create(session: Session, user: User) -> Profile:
    prof = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if prof is None:
        prof = Profile(user_id=user.id, headline=user.job_title)
        session.add(prof)
        session.commit()
        session.refresh(prof)
    return prof


def skills_of(session: Session, profile_id: uuid.UUID, confirmed_only: bool = False) -> list[ProfileSkill]:
    q = select(ProfileSkill).where(ProfileSkill.profile_id == profile_id)
    if confirmed_only:
        q = q.where(ProfileSkill.status == "confirmed")
    return list(session.exec(q.order_by(ProfileSkill.kind, col(ProfileSkill.confidence).desc(), ProfileSkill.name)))


def entries_of(session: Session, profile_id: uuid.UUID, confirmed_only: bool = False) -> list[ProfileEntry]:
    q = select(ProfileEntry).where(ProfileEntry.profile_id == profile_id)
    if confirmed_only:
        q = q.where(ProfileEntry.status == "confirmed")
    return list(session.exec(q.order_by(ProfileEntry.kind, col(ProfileEntry.start).desc())))


def last_extraction(session: Session, profile_id: uuid.UUID) -> ExtractionRun | None:
    return session.exec(select(ExtractionRun).where(ExtractionRun.profile_id == profile_id)
                        .order_by(col(ExtractionRun.id).desc())).first()


def own_skill(session: Session, prof: Profile, skill_id: int) -> ProfileSkill:
    s = session.get(ProfileSkill, skill_id)
    if s is None or s.profile_id != prof.id:  # control de propiedad
        raise HTTPException(status_code=404, detail="Competencia no encontrada")
    return s


def own_entry(session: Session, prof: Profile, entry_id: int) -> ProfileEntry:
    e = session.get(ProfileEntry, entry_id)
    if e is None or e.profile_id != prof.id:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return e


# ---------------------------------------------------------------------------
# Completitud y publicación
# ---------------------------------------------------------------------------
def completeness(prof: Profile, skills: list[ProfileSkill], entries: list[ProfileEntry]) -> tuple[int, list[dict]]:
    conf_t = sum(1 for s in skills if s.kind == "tech" and s.status == "confirmed")
    conf_p = sum(1 for s in skills if s.kind == "power" and s.status == "confirmed")
    conf_e = {k: sum(1 for e in entries if e.kind == k and e.status == "confirmed") for k in SECTION_KINDS}
    items = [
        ("Titular profesional", 10, bool(prof.headline)),
        ("Resumen", 10, bool(prof.summary)),
        ("3+ competencias técnicas confirmadas", 25, conf_t >= 3),
        ("2+ power skills confirmadas", 15, conf_p >= 2),
        ("Experiencia confirmada", 15, conf_e["experience"] >= 1),
        ("Formación confirmada", 10, conf_e["education"] >= 1),
        ("Años de experiencia", 5, prof.years_experience > 0),
        ("Certificaciones o idiomas", 10, conf_e["certification"] + conf_e["language"] >= 1),
    ]
    score = sum(w for _, w, ok in items if ok)
    return score, [{"label": label, "weight": w, "done": ok} for label, w, ok in items]


def publish_blockers(session: Session, prof: Profile, skills: list[ProfileSkill]) -> list[str]:
    blockers = []
    if not consent_service.has_processing(session, prof.user_id):
        blockers.append("Debe otorgar la autorización de tratamiento de datos.")
    need = int(get_setting(session, "min_confirmed_skills_to_publish") or 3)
    confirmed = sum(1 for s in skills if s.status == "confirmed")
    if confirmed < need:
        blockers.append(f"Confirme al menos {need} competencias (tiene {confirmed}).")
    return blockers


def touch(session: Session, prof: Profile) -> None:
    prof.updated_at = utcnow()
    session.add(prof)


def unpublish(session: Session, prof: Profile) -> None:
    prof.status, prof.published_at = "draft", None
    touch(session, prof)


# ---------------------------------------------------------------------------
# Fusión del resultado de extracción
# ---------------------------------------------------------------------------
def _norm_key(*parts: str | None) -> str:
    return norm(" ".join(p or "" for p in parts))


def apply_extraction(session: Session, prof: Profile, out: ExtractionOutput) -> ExtractionRun:
    p = out.profile
    run = ExtractionRun(profile_id=prof.id, file_hash=out.file_hash, file_size=out.file_size,
                        source_type=out.source_type, method=out.method[:160], provider=out.provider,
                        provider_model=out.provider_model, external_used=out.external_used, pages=out.pages,
                        ocr_used=out.ocr_used, sensitive_categories=out.sensitive,
                        warnings=out.warnings + ([out.external_note] if out.external_note else []),
                        stats=out.stats, quality={"completeness_raw": p["quality"].get("completeness"),
                                                  "sections": p["quality"].get("sections", [])},
                        suggested={"years_experience": p.get("years_experience", 0),
                                   "education_level": p.get("education_level", 0),
                                   "education_label": p.get("education_label"),
                                   "headline": p.get("headline"), "summary": p.get("summary")})
    session.add(run)
    session.flush()

    # 1) Se descartan los pendientes anteriores (lo confirmado, rechazado y manual se conserva)
    existing = skills_of(session, prof.id)
    for s in existing:
        if s.status == "pending" and s.origin != "manual":
            session.delete(s)
    keep = {(s.kind, s.key): s for s in existing if not (s.status == "pending" and s.origin != "manual")}
    for kind, items in (("tech", p["tech_skills"]), ("power", p["soft_skills"])):
        for it in items:
            prev = keep.get((kind, it["key"]))
            if prev is True:
                continue
            if prev is not None:
                if prev.status == "confirmed" and not prev.evidence and it.get("evidence"):
                    prev.evidence = it["evidence"][:300]
                    session.add(prev)
                continue  # rechazado o confirmado: no se vuelve a proponer
            session.add(ProfileSkill(profile_id=prof.id, kind=kind, key=it["key"][:120], name=it["name"][:120],
                                     origin=it.get("origin", "extracted"), status="pending",
                                     confidence=it.get("confidence"), evidence=(it.get("evidence") or "")[:300] or None,
                                     source=(it.get("source") or "")[:80] or None, extraction_id=run.id))
            keep[(kind, it["key"])] = True  # evita duplicados dentro del mismo CV

    # 2) Entradas (experiencia, educación, certificaciones, idiomas)
    old_entries = entries_of(session, prof.id)
    for e in old_entries:
        if e.status == "pending" and e.origin != "manual":
            session.delete(e)
    seen = {(e.kind, _norm_key(e.title, e.organization)) for e in old_entries
            if not (e.status == "pending" and e.origin != "manual")}

    def add_entry(kind: str, title: str, origin: str = "extracted", **kw) -> None:
        title = clean_display(title)[:200]
        if len(title) < 2:
            return
        k = (kind, _norm_key(title, kw.get("organization")))
        if k in seen:
            return
        seen.add(k)
        session.add(ProfileEntry(profile_id=prof.id, kind=kind, title=title, origin=origin, status="pending",
                                 extraction_id=run.id, **kw))

    for e in p.get("experience", []):
        add_entry("experience", e.get("role") or "Experiencia", organization=(e.get("company") or None),
                  start=e.get("start") or None, end=e.get("end") or None, current=bool(e.get("current")),
                  years=e.get("years"), evidence=(e.get("period") or "")[:300] or None)
    for e in p.get("education", []):
        add_entry("education", e.get("text", ""), level=EDU_LEVELS.get(e.get("level", 0)) if e.get("level") else None,
                  evidence=e.get("text", "")[:300])
    for c in p.get("certifications", []):
        add_entry("certification", c if isinstance(c, str) else c.get("title", ""), evidence=(c if isinstance(c, str) else "")[:300])
    for c in p.get("ai_certifications", []):
        add_entry("certification", c["title"], origin=c.get("origin", "ai_external"), evidence=c.get("evidence"))
    for lang in p.get("languages", []):
        add_entry("language", lang.get("language", ""), level=lang.get("level"))

    # 3) Valores sugeridos: se aplican solo si el empleado no los fijó manualmente
    if prof.years_source != "manual" and p.get("years_experience"):
        prof.years_experience, prof.years_source = float(p["years_experience"]), "extracted"
    if prof.education_source != "manual" and p.get("education_level"):
        prof.education_level, prof.education_source = int(p["education_level"]), "extracted"
    if not prof.headline and p.get("headline"):
        prof.headline = clean_display(p["headline"])[:160]
    if not prof.summary and p.get("summary"):
        prof.summary = p["summary"][:1200]
    prof.last_source_type = out.source_type
    touch(session, prof)
    return run


# ---------------------------------------------------------------------------
# Edición manual
# ---------------------------------------------------------------------------
def make_skill(prof: Profile, kind: str, name: str, level: int | None) -> ProfileSkill:
    if kind == "tech":
        key = canonical_tech(name)
        label = display_tech(key) if key else clean_display(name)
    else:
        sk = canonical_soft(name)
        key = sk or norm(name)
        label = soft_label(sk) if sk else clean_display(name).capitalize()
    return ProfileSkill(profile_id=prof.id, kind=kind, key=key[:120], name=label[:120], origin="manual",
                        status="confirmed", confidence=None, level=level, confirmed_at=utcnow(),
                        source="Agregada por el empleado")


def entry_years(start: str | None, end: str | None, current: bool) -> float | None:
    if not start:
        return None
    try:
        y1, m1 = map(int, start.split("-"))
        if current or not end:
            now = utcnow()
            y2, m2 = now.year, now.month
        else:
            y2, m2 = map(int, end.split("-"))
    except ValueError:
        return None
    months = (y2 * 12 + m2) - (y1 * 12 + m1)
    return round(max(0, months) / 12, 1)


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------
def _skill_out(s: ProfileSkill) -> SkillOut:
    return SkillOut(id=s.id, kind=s.kind, key=s.key, name=s.name, origin=s.origin, status=s.status,
                    confidence=s.confidence, confidence_label=confidence_label(s.confidence), evidence=s.evidence,
                    source=s.source, level=s.level)


def _entry_out(e: ProfileEntry) -> EntryOut:
    return EntryOut(id=e.id, kind=e.kind, title=e.title, organization=e.organization, start=e.start, end=e.end,
                    current=e.current, years=e.years, level=e.level, origin=e.origin, status=e.status, evidence=e.evidence)


def extraction_out(r: ExtractionRun) -> ExtractionOut:
    return ExtractionOut(id=r.id, created_at=r.created_at, source_type=r.source_type, method=r.method,
                         provider=r.provider, provider_model=r.provider_model, external_used=r.external_used,
                         pages=r.pages, ocr_used=r.ocr_used, sensitive_categories=r.sensitive_categories,
                         warnings=r.warnings, stats=r.stats, quality=r.quality, suggested=r.suggested,
                         file_size=r.file_size)


def owner_view(session: Session, prof: Profile, user: User) -> ProfileOut:
    skills = skills_of(session, prof.id)
    entries = entries_of(session, prof.id)
    score, breakdown = completeness(prof, skills, entries)
    c = consent_service.current(session, user.id)
    blockers = publish_blockers(session, prof, skills)
    last = last_extraction(session, prof.id)
    return ProfileOut(
        id=prof.id, user_id=user.id, full_name=decrypt(user.full_name_enc) or "—", email=decrypt(user.email_enc),
        department=user.department, job_title=user.job_title, headline=prof.headline, summary=prof.summary,
        years_experience=prof.years_experience, years_source=prof.years_source, education_level=prof.education_level,
        education_label=EDU_LEVELS.get(prof.education_level, "No especificado"), education_source=prof.education_source,
        status=prof.status, published_at=prof.published_at, visibility=prof.visibility,
        open_to_mobility=prof.open_to_mobility, completeness=score, completeness_breakdown=breakdown,
        skills=[_skill_out(s) for s in skills], entries=[_entry_out(e) for e in entries], updated_at=prof.updated_at,
        last_extraction=extraction_out(last) if last else None,
        consent={"processing": bool(c and c.processing), "external_ai": bool(c and c.external_ai),
                 "granted_at": c.granted_at.isoformat() if c else None, "policy_version": c.policy_version if c else None},
        can_publish=not blockers, publish_blockers=blockers,
    )


def published_view(session: Session, prof: Profile, user: User) -> ProfileOut:
    """Lo que ve RR. HH.: solo elementos confirmados y secciones visibles. Sin correo."""
    skills = skills_of(session, prof.id, confirmed_only=True)
    vis = prof.visibility or {}
    entries = [e for e in entries_of(session, prof.id, confirmed_only=True) if vis.get(e.kind, True)]
    score, breakdown = completeness(prof, skills, entries)
    return ProfileOut(
        id=prof.id, user_id=user.id, full_name=decrypt(user.full_name_enc) or "—", email=None,
        department=user.department, job_title=user.job_title, headline=prof.headline,
        summary=prof.summary if vis.get("summary", True) else None, years_experience=prof.years_experience,
        years_source=prof.years_source, education_level=prof.education_level,
        education_label=EDU_LEVELS.get(prof.education_level, "No especificado"), education_source=prof.education_source,
        status=prof.status, published_at=prof.published_at, visibility=vis, open_to_mobility=prof.open_to_mobility,
        completeness=score, completeness_breakdown=breakdown, skills=[_skill_out(s) for s in skills],
        entries=[_entry_out(e) for e in entries], updated_at=prof.updated_at,
    )


def published_profiles(session: Session) -> list[tuple[Profile, User]]:
    """Perfiles publicados de usuarios activos con autorización vigente (requisito para que RR. HH. los vea)."""
    rows = session.exec(select(Profile, User).join(User, User.id == Profile.user_id)
                        .where(Profile.status == "published", User.is_active == True, User.role == "employee")).all()  # noqa: E712
    return [(p, u) for p, u in rows if consent_service.has_processing(session, u.id)]


def get_published(session: Session, profile_id: uuid.UUID) -> tuple[Profile, User]:
    prof = session.get(Profile, profile_id)
    user = session.get(User, prof.user_id) if prof else None
    if (prof is None or user is None or prof.status != "published" or not user.is_active
            or not consent_service.has_processing(session, user.id)):
        raise HTTPException(status_code=404, detail="Perfil no disponible")
    return prof, user


def talent_card(session: Session, prof: Profile, user: User, active_paths: int = 0) -> TalentCard:
    skills = skills_of(session, prof.id, confirmed_only=True)
    entries = entries_of(session, prof.id, confirmed_only=True)
    score, _ = completeness(prof, skills, entries)
    tech = [s for s in skills if s.kind == "tech"]
    power = [s for s in skills if s.kind == "power"]
    return TalentCard(profile_id=prof.id, full_name=decrypt(user.full_name_enc) or "—", department=user.department,
                      job_title=user.job_title, headline=prof.headline, years_experience=prof.years_experience,
                      education_label=EDU_LEVELS.get(prof.education_level, "No especificado"),
                      top_tech=[s.name for s in tech[:6]], top_power=[s.name for s in power[:4]],
                      tech_count=len(tech), power_count=len(power),
                      certifications=sum(1 for e in entries if e.kind == "certification"), completeness=score,
                      open_to_mobility=prof.open_to_mobility, published_at=prof.published_at, active_paths=active_paths)


def export_all(session: Session, prof: Profile, user: User) -> dict:
    """Derecho de acceso / portabilidad: todo lo que el sistema guarda del titular."""
    from app.modules.development.models import LearningItem, LearningPath
    from app.modules.matching.models import DECISION_LABELS, HRDecision

    view = owner_view(session, prof, user).model_dump(mode="json")
    paths = []
    for lp in session.exec(select(LearningPath).where(LearningPath.profile_id == prof.id)):
        items = session.exec(select(LearningItem).where(LearningItem.path_id == lp.id)).all()
        paths.append({"title": lp.title, "status": lp.status, "items": [
            {"skill": i.skill, "course": i.course_title, "status": i.status, "progress": i.progress} for i in items]})
    decisions = [{"position_id": d.position_id, "decision": DECISION_LABELS.get(d.decision, d.decision),
                  "date": d.created_at.isoformat()} for d in
                 session.exec(select(HRDecision).where(HRDecision.profile_id == prof.id))]
    return {
        "generated_at": utcnow().isoformat(), "profile": view,
        "extractions": [extraction_out(r).model_dump(mode="json") for r in
                        session.exec(select(ExtractionRun).where(ExtractionRun.profile_id == prof.id))],
        "consents": [{"granted_at": c.granted_at.isoformat(), "processing": c.processing, "external_ai": c.external_ai,
                      "policy_version": c.policy_version, "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None}
                     for c in consent_service.history(session, user.id)],
        "learning_paths": paths, "hr_decisions": decisions,
        "note": "El archivo original del CV no se almacena; solo su huella SHA-256.",
    }


def wipe_profile_data(session: Session, prof: Profile) -> None:
    """Supresión del contenido del perfil (se conserva la cuenta)."""
    for model in (ProfileSkill, ProfileEntry, ExtractionRun):
        for row in session.exec(select(model).where(model.profile_id == prof.id)):
            session.delete(row)
    prof.headline = prof.summary = None
    prof.years_experience, prof.years_source, prof.education_level, prof.education_source = 0, "none", 0, "none"
    unpublish(session, prof)
