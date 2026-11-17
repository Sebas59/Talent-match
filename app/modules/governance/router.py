"""Tarjeta ética y de gobernanza: contenido explicativo + indicadores calculados desde la BD."""
from collections import Counter
from functools import lru_cache
from statistics import mean

from fastapi import APIRouter
from sqlmodel import func, select

from app.core.database import SessionDep
from app.modules.auth.deps import CurrentUser, HROrAdmin
from app.modules.consent.models import Consent
from app.modules.matching.models import HRDecision, MatchResult
from app.modules.profiles.models import ExtractionRun, ProfileSkill

router = APIRouter(prefix="/governance", tags=["gobernanza"])

CARD = [
    {"id": "consent", "title": "Consentimiento del empleado",
     "body": "El propio empleado otorga o retira la autorización desde su espacio. Sin autorización no se procesa su "
             "hoja de vida y RR. HH. no ve su perfil. Cada cambio queda registrado con fecha y versión de la política."},
    {"id": "purpose", "title": "Finalidad del tratamiento",
     "body": "Los datos se usan solo para gestión de talento interno: perfil profesional, compatibilidad con cargos, "
             "brechas y formación. No se usan para evaluación de desempeño, nómina ni decisiones disciplinarias."},
    {"id": "protection", "title": "Protección de información personal",
     "body": "Nombre y correo cifrados con Fernet; búsqueda por índice HMAC; contraseñas Argon2id; el archivo del CV no "
             "se guarda (solo su huella SHA-256); datos sensibles detectados y descartados; bitácora encadenada."},
    {"id": "external_ai", "title": "Uso de proveedores externos de IA",
     "body": "Desactivado salvo que el empleado lo autorice por separado y la organización lo permita. Antes del envío "
             "se eliminan correo, teléfono, URLs, documentos y datos sensibles. Sin clave configurada se usa el modo local."},
    {"id": "explainability", "title": "Explicabilidad de los resultados",
     "body": "Cada porcentaje muestra componentes, pesos efectivos, requisitos cumplidos, parciales y faltantes, "
             "evidencias del perfil y el cálculo aplicado."},
    {"id": "correction", "title": "Posibilidad de corregir información",
     "body": "El empleado revisa cada competencia y registro extraído: lo confirma, lo corrige o lo rechaza. Solo lo "
             "confirmado se publica y participa en el matching."},
    {"id": "limits", "title": "Limitaciones del modelo",
     "body": "La extracción es heurística; los niveles de confianza no son probabilidades calibradas. El catálogo de "
             "competencias proviene de ofertas en inglés. El puntaje refleja información declarada, no capacidad real."},
    {"id": "bias", "title": "Prevención de sesgos",
     "body": "El matching solo usa competencias, experiencia, formación y certificaciones. No usa nombre, edad, género, "
             "foto, estado civil, origen, salud ni departamento. Se vigila la brecha de puntaje por tipo de documento."},
    {"id": "oversight", "title": "Supervisión humana",
     "body": "El sistema ordena y explica; no asigna. Toda decisión la registra una persona de RR. HH. con una "
             "justificación de al menos 20 caracteres, y el empleado puede consultarla."},
    {"id": "traceability", "title": "Trazabilidad de decisiones",
     "body": "Ejecuciones de matching, decisiones, consentimientos y accesos a perfiles quedan en una bitácora sin datos "
             "personales, con cadena de hashes verificable por el administrador."},
]


@router.get("/card")
def card(_: CurrentUser):
    return {"principle": "La IA recomienda; las personas responsables deciden.", "items": CARD,
            "disclaimer": "Esta tarjeta describe controles implementados en el software. No constituye una "
                          "certificación de cumplimiento normativo."}


@router.get("/metrics")
def metrics(session: SessionDep, _: HROrAdmin):
    consents = session.exec(select(Consent).where(Consent.revoked_at == None)).all()  # noqa: E711
    runs = session.exec(select(ExtractionRun)).all()
    sens = Counter(c for r in runs for c in r.sensitive_categories)
    skills = session.exec(select(ProfileSkill)).all()
    by_origin = Counter(s.origin for s in skills)
    by_status = Counter(s.status for s in skills)
    # Equidad: puntaje promedio por tipo de documento de origen (no debe penalizar escaneados u otros formatos)
    from app.modules.profiles.models import Profile
    src = {}
    for r in session.exec(select(MatchResult)).all():
        p = session.get(Profile, r.profile_id)
        key = (p.last_source_type or "manual") if p else "manual"
        src.setdefault(key, []).append(r.score)
    avg = {k: round(mean(v), 1) for k, v in src.items() if v}
    gap = round(max(avg.values()) - min(avg.values()), 1) if len(avg) > 1 else 0.0
    n_results = session.exec(select(func.count()).select_from(MatchResult)).one()
    decided = session.exec(select(func.count(func.distinct(HRDecision.match_result_id)))).one()
    return {
        "consents_active": sum(1 for c in consents if c.processing),
        "external_ai_authorized": sum(1 for c in consents if c.external_ai),
        "extractions": len(runs), "external_extractions": sum(1 for r in runs if r.external_used),
        "sensitive_discarded": dict(sens),
        "skills_by_origin": dict(by_origin), "skills_by_status": dict(by_status),
        "confirmed_pct": round(by_status.get("confirmed", 0) / len(skills) * 100, 1) if skills else 0.0,
        "fairness_by_source": avg, "fairness_gap": gap, "fairness_alert": gap > 10,
        "match_results": n_results, "human_decisions": session.exec(select(func.count()).select_from(HRDecision)).one(),
        "results_with_decision": decided,
        "automatic_decisions": 0,
    }


@lru_cache(maxsize=1)
def _benchmark() -> dict:
    from app.modules.governance.benchmark import extraction_benchmark
    return extraction_benchmark()


@router.get("/benchmark")
def benchmark(_: HROrAdmin):
    return _benchmark()
