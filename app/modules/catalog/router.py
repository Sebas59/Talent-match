"""Catálogo de solo lectura: plantillas de cargos (JobsDatasetProcessed.csv) y vocabulario de competencias."""
import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import SessionDep
from app.core.text import norm
from app.modules.auth.deps import CurrentUser, HR
from app.modules.catalog import skills as catalog

router = APIRouter(prefix="/catalog", tags=["catálogo"])


class TemplateSearch(BaseModel):
    """POST con body (V5): los términos no quedan en URLs, logs de proxy ni historial."""
    query: str = Field(default="", max_length=80)
    limit: int = Field(default=12, ge=1, le=40)


@router.post("/job-templates/search")
def search_templates(body: TemplateSearch, _: HR):
    q = norm(body.query)
    out = []
    for req in catalog.all_job_requirements():
        if len(req["tech_skills"]) < 3:
            continue
        if q and q not in norm(req["title"]) and q not in norm(req["category"]):
            continue
        out.append({"job_id": req["job_id"], "title": req["title"], "category": req["category"],
                    "min_years": req["min_years"], "education_level": req["education_level"],
                    "education_label": req["education_label"], "tech": [t["name"] for t in req["tech_skills"]][:12],
                    "power": [s["name"] for s in req["soft_skills"]][:6], "summary": req["summary"][:260]})
        if len(out) >= body.limit:
            break
    return {"items": out, "source": "JobsDatasetProcessed.csv (ofertas reales de referencia, idioma inglés)"}


@router.get("/job-templates/{job_id}")
def template(job_id: int, _: HR):
    for req in catalog.all_job_requirements():
        if req["job_id"] == job_id:
            return {
                "job_id": job_id, "title": req["title"], "category": req["category"], "summary": req["summary"],
                "min_years": req["min_years"], "education_level": req["education_level"],
                "requirements": [{"kind": "tech", "name": t["name"],
                                  "importance": "mandatory" if t["weight"] >= 1 and i < 3 else "desirable",
                                  "weight": t["weight"]} for i, t in enumerate(req["tech_skills"][:12])]
                + [{"kind": "power", "name": s["name"], "importance": "desirable", "weight": s["weight"]}
                   for s in req["soft_skills"][:6]],
            }
    raise HTTPException(status_code=404, detail="Plantilla no encontrada")


@router.get("/skills")
def skills(_: CurrentUser, q: Annotated[str, Query(max_length=60)] = "",
           kind: Annotated[str, Query(pattern="^(tech|power)$")] = "tech",
           limit: Annotated[int, Query(ge=1, le=30)] = 12):
    """Autocompletado de competencias (los términos son vocabulario, no datos personales)."""
    nq = norm(q)
    if kind == "power":
        items = [{"key": k, "name": v["label"]} for k, v in catalog.SOFT_CANON.items()]
        if nq:
            items = [i for i in items if nq in norm(i["name"]) or nq in i["key"]
                     or any(nq in norm(s) for s in catalog.SOFT_CANON[i["key"]]["syn"])]
        return items[:limit]
    freq = catalog.tech_frequency()
    vocab = sorted({v for v in catalog.tech_vocabulary().values()}, key=lambda k: -freq.get(k, 0))
    if nq:
        rx = re.compile(r"(^|\s)" + re.escape(nq))
        vocab = [k for k in vocab if rx.search(k)]
    return [{"key": k, "name": catalog.display_tech(k)} for k in vocab[:limit]]


@router.get("/defaults")
def defaults(session: SessionDep, _: HR):
    """Valores por defecto que RR. HH. necesita al crear cargos (configurados por el administrador)."""
    from app.modules.admin.settings import get_setting
    from app.modules.matching.engine import normalize_weights
    return {"weights": normalize_weights(get_setting(session, "default_weights")),
            "availability_threshold": get_setting(session, "availability_threshold")}
