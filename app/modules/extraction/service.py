"""Orquestación de la extracción: archivo → texto → descarte de sensibles → parser local → IA externa opcional.

Distinción de transparencia exigida para V6:
  extracted   = encontrado literalmente en el documento
  inferred    = deducido (de logros por el parser local, o por un modelo con evidencia verificada)
  ai_external = propuesto por un proveedor externo; el nombre no aparece literal pero la evidencia sí
  manual      = agregado por el empleado
El estado "confirmed" lo asigna únicamente el empleado.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.core.text import redact_pii
from app.modules.extraction import providers as provider_registry
from app.modules.extraction.cv_parser import parse_text
from app.modules.extraction.document_reader import read_image, read_pdf
from app.modules.extraction.json_reader import read_json
from app.modules.extraction.providers.base import ProviderResult, parse_payload, verify_items
from app.modules.extraction.sensitive import redact_for_external, redact_sensitive

log = logging.getLogger("talentmatch.extraction")

ALLOWED = {".pdf": "pdf", ".json": "json", ".png": "image", ".jpg": "image", ".jpeg": "image"}
MAX_CHARS = 30_000
LOCAL_METHOD = "Parser local determinista con evidencia (catálogo ES↔EN de 3.000 ofertas)"


class InvalidDocument(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class ExtractionOutput:
    file_hash: str
    file_size: int
    source_type: str
    method: str
    pages: int
    ocr_used: bool
    sensitive: list[str]
    warnings: list[str]
    profile: dict
    provider: str = "local"
    provider_model: str | None = None
    external_used: bool = False
    external_note: str = ""
    stats: dict = field(default_factory=dict)


def _origin_of(source: str) -> str:
    return "inferred" if "Inferida" in (source or "") else "extracted"


def validate(filename: str, data: bytes) -> str:
    s = get_settings()
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise InvalidDocument("Formato no permitido. Use PDF, JSON, PNG o JPG.", 415)
    if not data:
        raise InvalidDocument("El archivo está vacío.")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise InvalidDocument(f"El archivo supera {s.max_upload_mb} MB.", 413)
    kind = ALLOWED[ext]
    # Verificación por firma (no se confía en la extensión ni en el Content-Type)
    if kind == "pdf" and not data.startswith(b"%PDF-"):
        raise InvalidDocument("El archivo no es un PDF válido.", 415)
    if kind == "image" and not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")):
        raise InvalidDocument("La imagen no es PNG ni JPG válida.", 415)
    if kind == "json":
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InvalidDocument("El JSON no es válido.", 415)
    return kind


def _read(kind: str, data: bytes) -> tuple[str, dict, list[str], str, str, int, bool, list[str]]:
    """Devuelve texto, declarado, sensibles, tipo, método, páginas, ocr, advertencias."""
    s = get_settings()
    if kind == "json":
        try:
            text, declared, sensitive = read_json(data)
        except ValueError as exc:
            raise InvalidDocument(str(exc)) from exc
        return text, declared, list(sensitive), "json", "Lectura estructurada de JSON", 1, False, []
    if kind == "pdf":
        try:
            import pdfplumber  # noqa: F401
            rr = read_pdf(data, max_pages=s.max_pdf_pages)
        except InvalidDocument:
            raise
        except Exception as exc:  # PDF cifrado, corrupto o malformado
            raise InvalidDocument("No se pudo leer el PDF (¿cifrado o dañado?).", 415) from exc
        sens = ["Fotografía"] if rr.photo_detected else []
        warnings = list(rr.warnings)
        if rr.pages > s.max_pdf_pages:
            warnings.append(f"Solo se analizaron las primeras {s.max_pdf_pages} páginas.")
        return rr.text, {}, sens, rr.source_type, rr.method, rr.pages, rr.ocr_used, warnings
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 40_000_000  # protección contra bombas de descompresión
    try:
        rr = read_image(data)
    except Exception as exc:
        raise InvalidDocument("No se pudo leer la imagen.", 415) from exc
    return rr.text, {}, [], rr.source_type, rr.method, 1, rr.ocr_used, list(rr.warnings)


def run_extraction(filename: str, data: bytes, *, allow_external: bool, preferred_provider: str = "auto",
                   provider=None) -> ExtractionOutput:
    kind = validate(filename, data)
    file_hash = hashlib.sha256(data).hexdigest()
    text, declared, sensitive, source_type, method, pages, ocr, warnings = _read(kind, data)
    text = (text or "")[:MAX_CHARS]
    if len(text.strip()) < 40:
        raise InvalidDocument("No fue posible leer contenido suficiente del documento. " + " ".join(warnings))

    clean_text, found = redact_sensitive(text)
    for f in found:
        if f not in sensitive:
            sensitive.append(f)
    profile = parse_text(clean_text, declared)
    if profile.get("references_omitted") and "Referencias de terceros" not in sensitive:
        sensitive.append("Referencias de terceros")
    for s_ in profile["tech_skills"] + profile["soft_skills"]:
        s_["origin"] = _origin_of(s_.get("source"))

    out = ExtractionOutput(file_hash=file_hash, file_size=len(data), source_type=source_type,
                           method=LOCAL_METHOD + f" · {method}", pages=pages, ocr_used=ocr, sensitive=sensitive,
                           warnings=warnings + profile["quality"]["warnings"], profile=profile)

    # IA externa: solo con autorización del titular + política de la organización + proveedor configurado
    if allow_external:
        prov = provider or provider_registry.select_provider(preferred_provider)
        if prov is None:
            out.external_note = "No hay proveedor externo configurado; se usó solo la extracción local."
        else:
            res = _call_external(prov, clean_text)
            out.external_note = res.note
            if res.used:
                out.provider, out.provider_model, out.external_used = prov.name, prov.model, True
                out.method += f" + {prov.name} ({prov.model}) con evidencia verificada"
                known_t = {s_["key"] for s_ in profile["tech_skills"]}
                known_s = {s_["key"] for s_ in profile["soft_skills"]}
                profile["tech_skills"] += [x for x in res.tech if x["key"] not in known_t]
                profile["soft_skills"] += [x for x in res.soft if x["key"] not in known_s]
                known_c = {c.lower() for c in profile.get("certifications", [])}
                profile.setdefault("ai_certifications", [])
                for c in res.certifications:
                    if c["title"].lower() not in known_c:
                        profile["ai_certifications"].append(c)
                out.stats["external_proposed"] = res.proposed
                out.stats["external_rejected"] = res.rejected

    out.stats.update({
        "tech": len(profile["tech_skills"]), "power": len(profile["soft_skills"]),
        "extracted": sum(1 for x in profile["tech_skills"] + profile["soft_skills"] if x["origin"] == "extracted"),
        "inferred": sum(1 for x in profile["tech_skills"] + profile["soft_skills"] if x["origin"] in ("inferred", "ai_external")),
        "experience": len(profile.get("experience", [])), "education": len(profile.get("education", [])),
        "certifications": len(profile.get("certifications", [])) + len(profile.get("ai_certifications", [])),
        "languages": len(profile.get("languages", [])), "sensitive_discarded": len(sensitive),
    })
    return out


def _call_external(prov, clean_text: str) -> ProviderResult:
    safe = redact_pii(redact_for_external(clean_text))[:12_000]
    try:
        raw = prov.call(safe)
        payload = parse_payload(raw)
    except Exception as exc:  # la extracción local siempre responde
        log.warning("Proveedor %s no disponible: %s", prov.name, type(exc).__name__)
        return ProviderResult(used=False, provider=prov.name, model=prov.model,
                              note=f"El proveedor {prov.name} no respondió correctamente; se usó la extracción local.")
    return verify_items(payload, clean_text, prov.name, prov.model)
