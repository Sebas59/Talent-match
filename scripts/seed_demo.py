"""Carga reproducible de datos de demostración.

Uso (PowerShell, desde la carpeta del proyecto):
    python -m scripts.seed_demo            # carga si la base está vacía
    python -m scripts.seed_demo --reset    # borra y vuelve a cargar (solo si la base contiene únicamente datos demo)

Protecciones:
  - Se niega a ejecutarse con ENVIRONMENT=production o DEMO_MODE=false.
  - --reset se niega si existen usuarios que no son de demostración (salvo --force explícito).
  - Los perfiles se construyen pasando CV sintéticos en PDF por el MISMO pipeline de extracción de la app.
"""
from __future__ import annotations

import argparse
import io
import sys
import textwrap
from pathlib import Path

from sqlmodel import Session, func, select

from app.core.config import BASE_DIR, get_settings
from app.core.database import create_db_and_tables, drop_all, engine
from app.core.time import utcnow
from scripts import demo_data as D

CV_DIR = BASE_DIR / "demo" / "cvs"


# ---------------------------------------------------------------------------
# CV sintéticos
# ---------------------------------------------------------------------------
def cv_text(spec: dict) -> str:
    first = spec["slug"].split(".")[0]
    lines = [spec["name"].upper(), spec["headline"],
             f"{spec['slug']}@correo-ficticio.example | +57 300 555 {abs(hash(first)) % 9000 + 1000} | Bogotá, Colombia"]
    lines += spec.get("sensitive", [])
    lines += ["", "PERFIL PROFESIONAL", spec["profile"], "", "EXPERIENCIA LABORAL"]
    for role, period, desc in spec["experience"]:
        lines += [f"{role}  {period}", desc]
    lines += ["", "FORMACIÓN ACADÉMICA", *spec["education"], "", "HABILIDADES TÉCNICAS", spec["skills"], "",
              "HABILIDADES BLANDAS", spec["soft"]]
    if spec.get("certs"):
        lines += ["", "CERTIFICACIONES", *spec["certs"]]
    lines += ["", "IDIOMAS", spec["languages"], "", "REFERENCIAS", "Disponibles a solicitud."]
    return "\n".join(lines)


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("CV sintético de demostración")
    y = 750
    for raw in text.splitlines():
        heading = raw.isupper() and len(raw) < 40
        c.setFont("Helvetica-Bold" if heading else "Helvetica", 12 if heading else 10)
        for chunk in (textwrap.wrap(raw, 95) or [""]):
            if y < 60:
                c.showPage()
                y = 750
            c.drawString(50, y, chunk)
            y -= 15
        if heading:
            y -= 2
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
def _guard(reset: bool, force: bool) -> None:
    s = get_settings()
    if s.is_production or not s.demo_mode:
        sys.exit("Semilla demo deshabilitada: ENVIRONMENT=production o DEMO_MODE=false.")
    create_db_and_tables()
    from app.modules.auth.models import User

    with Session(engine) as session:
        real = session.exec(select(func.count()).select_from(User).where(User.is_demo == False)).one()  # noqa: E712
        total = session.exec(select(func.count()).select_from(User)).one()
    if reset:
        if real and not force:
            sys.exit(f"Se encontraron {real} usuarios que NO son de demostración. No se borrará nada. "
                     "Use --force solo si está seguro de que es una base de pruebas.")
        drop_all()
        create_db_and_tables()
    elif total:
        sys.exit("La base ya tiene datos. Use --reset para recargar la demostración.")


def seed(reset: bool = False, force: bool = False, quiet: bool = False) -> dict:
    _guard(reset, force)
    from app.modules.audit.service import log_event
    from app.modules.auth.models import Invitation
    from app.modules.auth.service import create_user
    from app.modules.consent import service as consent
    from app.modules.development import service as dev
    from app.modules.extraction.service import run_extraction
    from app.modules.matching import service as matching
    from app.modules.matching.models import HRDecision, MatchResult
    from app.modules.privacy.models import PrivacyRequest
    from app.modules.profiles import service as profiles
    from app.modules.projects.models import Position, Project
    from app.modules.projects.schemas import RequirementIn
    from app.modules.projects.service import next_code, set_requirements
    from app.core.crypto import blind_index, encrypt, new_token, token_hash

    say = (lambda *a: None) if quiet else print
    CV_DIR.mkdir(parents=True, exist_ok=True)
    out = {"users": 0, "profiles": 0, "projects": 0, "positions": 0, "runs": 0}
    with Session(engine) as session:
        admin = create_user(session, email=D.ADMIN["email"], full_name=D.ADMIN["name"], password=D.ADMIN["password"],
                            role="admin", department=D.ADMIN["department"], job_title=D.ADMIN["job_title"], is_demo=True)
        hr = [create_user(session, email=h["email"], full_name=h["name"], password=h["password"], role="hr",
                          department=h["department"], job_title=h["job_title"], is_demo=True) for h in D.HR_USERS]
        out["users"] += 1 + len(hr)
        log_event(session, actor=admin.id, actor_role="admin", action="demo_seed_start", resource="system",
                  category="admin", detail="Carga de datos sintéticos de demostración")

        emp = {}
        for spec in D.EMPLOYEES:
            u = create_user(session, email=f"{spec['slug']}@{D.ORG_DOMAIN}", full_name=spec["name"],
                            password=D.EMPLOYEE_PASSWORD, role="employee", department=spec["department"],
                            job_title=spec["job_title"], is_demo=True, invited_by=hr[0].id)
            consent.record(session, u.id, True, bool(spec.get("external_ai")), None)
            prof = profiles.get_or_create(session, u)
            pdf = make_pdf(cv_text(spec))
            (CV_DIR / f"cv_{spec['slug'].replace('.', '_')}.pdf").write_bytes(pdf)
            ex = run_extraction(f"{spec['slug']}.pdf", pdf, allow_external=False)
            profiles.apply_extraction(session, prof, ex)
            session.commit()
            if spec["publish"]:
                for s in profiles.skills_of(session, prof.id):
                    if s.status == "pending" and (s.confidence or 0) >= 0.75:
                        s.status, s.confirmed_at = "confirmed", utcnow()
                        session.add(s)
                for e in profiles.entries_of(session, prof.id):
                    if e.status == "pending":
                        e.status = "confirmed"
                        session.add(e)
                prof.status, prof.published_at = "published", utcnow()
                session.add(prof)
            session.commit()
            log_event(session, actor=u.id, actor_role="employee", action="cv_processed", resource="extraction",
                      category="data", detail=f"tipo={ex.source_type}; proveedor=local; semilla demo")
            if spec["publish"]:
                log_event(session, actor=u.id, actor_role="employee", action="profile_published", resource="profile",
                          category="data", detail="semilla demo")
            emp[spec["slug"]] = (u, prof)
            out["users"] += 1
            out["profiles"] += 1
            say(f"  perfil {spec['name']}: {ex.stats.get('tech')} técnicas, {ex.stats.get('power')} power skills, "
                f"{len(ex.sensitive)} categorías sensibles descartadas")

        live = D.LIVE_EMPLOYEE
        create_user(session, email=f"{live['slug']}@{D.ORG_DOMAIN}", full_name=live["name"], password=D.EMPLOYEE_PASSWORD,
                    role="employee", department=live["department"], job_title=live["job_title"], is_demo=True,
                    invited_by=hr[0].id)
        (CV_DIR / "cv_demo_sofia_arango.pdf").write_bytes(make_pdf(cv_text(live)))
        out["users"] += 1

        raw = new_token()
        inv = D.PENDING_INVITE
        session.add(Invitation(token_hash=token_hash(raw), email_index=blind_index(inv["email"]),
                               email_enc=encrypt(inv["email"]), full_name_enc=encrypt(inv["name"]), role="employee",
                               department=inv["department"], job_title=inv["job_title"], invited_by=hr[0].id,
                               expires_at=utcnow().replace(year=utcnow().year + 1)))
        session.commit()
        out["invite_path"] = f"/invite/{raw}"

        # Proyectos, cargos y requisitos
        positions: dict[str, Position] = {}
        for pspec in D.PROJECTS:
            proj = Project(code=next_code(session), name=pspec["name"], area=pspec["area"], status=pspec["status"],
                           description=pspec["description"], start_date=pspec["start_date"], end_date=pspec["end_date"],
                           created_by=hr[0].id)
            session.add(proj)
            session.flush()
            out["projects"] += 1
            for ps in pspec["positions"]:
                from app.modules.matching.engine import normalize_weights
                from app.modules.admin.settings import DEFAULT_WEIGHTS

                source = None
                if ps.get("template"):
                    from app.modules.catalog.skills import all_job_requirements
                    source = next((j["job_id"] for j in all_job_requirements()
                                   if "mlops" in j["title"].lower() or "machine learning engineer" in j["title"].lower()), None)
                pos = Position(project_id=proj.id, title=ps["title"], seniority=ps.get("seniority"),
                               openings=ps.get("openings", 1), min_years=ps.get("min_years", 0),
                               min_years_mandatory=ps.get("min_years_mandatory", False),
                               education_level=ps.get("education_level", 0),
                               weights=normalize_weights(ps.get("weights") or DEFAULT_WEIGHTS), source_job_id=source,
                               description=f"Cargo del proyecto {pspec['name']}.", created_by=hr[0].id)
                session.add(pos)
                session.flush()
                set_requirements(session, pos, [RequirementIn(kind=k, name=n, importance=imp)
                                                for k, n, imp in ps["requirements"]])
                positions[ps["title"]] = pos
                out["positions"] += 1
            log_event(session, actor=hr[0].id, actor_role="hr", action="project_created", resource="project",
                      resource_id=str(proj.id), category="matching", detail="semilla demo", commit=False)
        session.commit()

        for pos in positions.values():
            run = matching.run_match(session, pos, hr[0])
            log_event(session, actor=hr[0].id, actor_role="hr", action="match_run", resource="position",
                      resource_id=str(pos.id), category="matching",
                      detail=f"evaluados={run.evaluated}; elegibles={run.eligible}; semilla demo")
            out["runs"] += 1

        def decide(position_title, slug, decision, justification, by=0):
            pos = positions[position_title]
            prof = emp[slug][1]
            run = matching.latest_run(session, pos.id)
            mr = session.exec(select(MatchResult).where(MatchResult.run_id == run.id,
                                                        MatchResult.profile_id == prof.id)).first()
            session.add(HRDecision(position_id=pos.id, profile_id=prof.id, match_result_id=mr.id if mr else None,
                                   decision=decision, justification=justification,
                                   score_at_decision=mr.score if mr else None, decided_by=hr[by].id))
            session.commit()
            log_event(session, actor=hr[by].id, actor_role="hr", action="hr_decision", resource="position",
                      resource_id=str(pos.id), category="matching", detail=f"decision={decision}; semilla demo")

        decide("Ingeniero(a) de Datos", "valentina.ospina", "interview",
               "Cumple los requisitos obligatorios y tiene experiencia liderando pipelines similares; validar disponibilidad con su líder.")
        decide("Desarrollador(a) Backend Java", "santiago.herrera", "shortlisted",
               "Experiencia directa en microservicios con Spring Boot en el dominio de pagos.")
        decide("Analista de Inteligencia de Negocio", "julian.restrepo", "selected",
               "Mejor ajuste al cargo y certificación vigente en Power BI; acordado con su jefatura actual.", by=1)
        decide("Analista de Inteligencia de Negocio", "paula.rios", "on_hold",
               "Perfil prometedor desde Finanzas; se propone ruta de formación en visualización antes de reconsiderar.")

        # Rutas de aprendizaje con progreso
        def path_for(slug, position_title, title, progress_values, by=0, self_assigned=False):
            u, prof = emp[slug]
            pos = positions[position_title]
            from app.modules.matching.engine import evaluate
            res = evaluate(matching.candidate_from_profile(session, prof), matching.spec_from_position(session, pos))
            lp = dev.create_path(session, profile_id=prof.id, title=title, gaps=res["gaps"],
                                 assigned_by=None if self_assigned else hr[by].id, position_id=pos.id,
                                 self_assigned=self_assigned, due_date="2027-03-31",
                                 note=None if self_assigned else "Ruta acordada en conversación de desarrollo.")
            for it, pv in zip(dev.path_items(session, lp.id), progress_values):
                dev.update_item(session, it, lp, None, pv)
            log_event(session, actor=(u.id if self_assigned else hr[by].id),
                      actor_role="employee" if self_assigned else "hr",
                      action="path_self_assigned" if self_assigned else "path_assigned", resource="learning_path",
                      resource_id=str(lp.id), category="development", detail="semilla demo")

        path_for("paula.rios", "Analista de Inteligencia de Negocio", "Ruta hacia Analista BI", [100, 60, 20])
        path_for("julian.restrepo", "Ingeniero(a) de Datos", "Ruta de crecimiento: Ingeniería de Datos", [40, 0, 0], by=1)
        path_for("camilo.vega", "Ingeniero(a) DevOps", "Ruta hacia Ingeniería DevOps", [100, 100, 30], self_assigned=True)
        path_for("mariana.cardenas", "Desarrollador(a) Backend Java", "Ruta full stack (backend)", [10])

        nat = emp["natalia.suarez"][0]
        session.add(PrivacyRequest(user_id=nat.id, type="access", status="resolved",
                                   detail_enc=encrypt("Quiero saber qué datos de mi CV se guardaron."),
                                   resolution_enc=encrypt("Se explicó que puede descargar todos sus datos desde Privacidad."),
                                   resolved_at=utcnow(), resolved_by=admin.id))
        cam = emp["camilo.vega"][0]
        session.add(PrivacyRequest(user_id=cam.id, type="objection",
                                   detail_enc=encrypt("¿Mi perfil se usa para evaluaciones de desempeño?")))
        session.commit()
        log_event(session, actor=admin.id, actor_role="admin", action="demo_seed_done", resource="system",
                  category="admin", detail=f"usuarios={out['users']}; perfiles={out['profiles']}; cargos={out['positions']}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga los datos de demostración de Talent Match V6")
    ap.add_argument("--reset", action="store_true", help="borra y recarga (solo bases de demostración)")
    ap.add_argument("--force", action="store_true", help="permite --reset aunque existan usuarios no demo")
    args = ap.parse_args()
    print("Cargando datos de demostración (el primer uso tarda mientras se indexa el catálogo)…")
    out = seed(args.reset, args.force)
    print(f"\nListo: {out['users']} usuarios, {out['profiles']} perfiles, {out['projects']} proyectos, "
          f"{out['positions']} cargos, {out['runs']} ejecuciones de matching.")
    print("CV sintéticos guardados en demo/cvs/. Use cv_demo_sofia_arango.pdf para la demostración en vivo.")
    print(f"Invitación pendiente (Martín Duque): http://localhost:8000{out['invite_path']}")
    print("\nCredenciales de DEMOSTRACIÓN (ver LEEME_V6.md):")
    print(f"  Administrador : {D.ADMIN['email']} / {D.ADMIN['password']}")
    for h in D.HR_USERS:
        print(f"  RR. HH.       : {h['email']} / {h['password']}")
    print(f"  Empleados     : <nombre.apellido>@{D.ORG_DOMAIN} / {D.EMPLOYEE_PASSWORD}  (p. ej. valentina.ospina@{D.ORG_DOMAIN})")
    print(f"  Flujo en vivo : sofia.arango@{D.ORG_DOMAIN} / {D.EMPLOYEE_PASSWORD}")


if __name__ == "__main__":
    main()
