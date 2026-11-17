"""Talent Match V6 — Monolito modular (FastAPI). Evolución directa de V5.

Lifespan: https://fastapi.tiangolo.com/advanced/events/
"""
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import create_db_and_tables, engine
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.modules.admin.router import router as admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.invitations import router as invitations_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.service import seed_admin
from app.modules.catalog.router import router as catalog_router
from app.modules.consent.router import router as consent_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.development.router import router as development_router
from app.modules.governance.router import router as governance_router
from app.modules.matching.router import router as matching_router
from app.modules.privacy.router import router as privacy_router
from app.modules.profiles.router import router as profiles_router
from app.modules.profiles.talent import router as talent_router
from app.modules.projects.router import router as projects_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("talentmatch")
settings = get_settings()

_catalog = {"status": "pending", "jobs": 0, "courses": 0, "seconds": None, "error": None}


def catalog_state() -> dict:
    return dict(_catalog)


def warm_catalog() -> None:
    """Carga datasets, vocabulario e índice TF-IDF (Iteración 4). Si falla, la app sigue funcionando."""
    t0 = time.time()
    _catalog["status"] = "loading"
    try:
        from app.modules.catalog.skills import all_job_requirements, tech_vocabulary
        from app.modules.development.recommender import warm
        from app.modules.extraction.cv_parser import _tech_regex

        tech_vocabulary()
        _tech_regex()
        _catalog["jobs"] = len(all_job_requirements())
        _catalog["courses"] = warm()
        _catalog["status"] = "ready"
    except Exception as exc:  # pragma: no cover - depende de los archivos en data/
        _catalog["status"], _catalog["error"] = "error", type(exc).__name__
        log.exception("No se pudo cargar el catálogo")
    _catalog["seconds"] = round(time.time() - t0, 1)
    log.info("Catálogo: %s (%s ofertas, %s cursos, %ss)", _catalog["status"], _catalog["jobs"],
             _catalog["courses"], _catalog["seconds"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        seed_admin(session)
    if settings.warm_catalog_on_start:
        threading.Thread(target=warm_catalog, name="warm-catalog", daemon=True).start()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    # En producción no se publica la superficie de ataque (docs/openapi)
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Orden: el último añadido es el más externo
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # nunca "*" con credenciales
    allow_credentials=True,                  # necesario para la cookie HttpOnly del refresh en desarrollo
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-TM-Refresh"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # No reflejar el input (podría contener datos personales)
    errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Error no controlado [%s]", getattr(request.state, "request_id", "-"))
    return JSONResponse(status_code=500, content={"detail": "Error interno",
                                                  "request_id": getattr(request.state, "request_id", None)})


API = "/api/v1"
for r in (auth_router, invitations_router, consent_router, profiles_router, talent_router, catalog_router,
          projects_router, matching_router, development_router, analytics_router, dashboard_router,
          privacy_router, admin_router, audit_router, governance_router):
    app.include_router(r, prefix=API)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "version": settings.app_version, "catalog": _catalog["status"],
            "demo_mode": settings.demo_mode and not settings.is_production}


# --------------------------- Frontend (SPA compilada) ---------------------------
DIST = Path(settings.frontend_dist)
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith(("api/", "docs", "openapi.json", "health")):
        raise HTTPException(status_code=404)
    candidate = (DIST / full_path).resolve()
    if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend no compilado. Ejecute: cd frontend; npm install; npm run build"},
                        status_code=503)
