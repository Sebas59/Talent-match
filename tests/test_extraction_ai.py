"""Extracción (formatos de Iteración 4), transparencia de origen y proveedores de IA intercambiables."""
import json
from pathlib import Path

import httpx
import pytest

from app.modules.extraction.document_reader import ocr_available
from app.modules.extraction.providers.base import parse_payload, verify_items
from app.modules.extraction.providers.gemini_provider import GeminiProvider
from app.modules.extraction.service import InvalidDocument, run_extraction

FIX = Path(__file__).parent / "fixtures"
GOLD = json.loads((FIX / "gold.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fname", ["cv_texto_data_engineer.pdf", "cv_json_resume.json", "cv_json_ats_es.json",
                                   "cv_escaneado_fullstack.pdf", "cv_imagen_fullstack.png"])
def test_formats_and_gold_recall(fname):
    if fname.endswith((".png",)) or "escaneado" in fname:
        if not ocr_available():
            pytest.skip("Tesseract no instalado: OCR no disponible en este equipo")
    out = run_extraction(fname, (FIX / fname).read_bytes(), allow_external=False)
    g = GOLD[fname]
    found = {s["key"] for s in out.profile["tech_skills"]}
    recall = len(found & set(g["tech"])) / len(g["tech"])
    assert recall >= 0.8, (fname, recall)
    assert set(g["sensitive"]) <= set(out.sensitive)
    assert g["years_min"] <= out.profile["years_experience"] <= g["years_max"]
    assert out.provider == "local" and not out.external_used
    assert {s["origin"] for s in out.profile["tech_skills"] + out.profile["soft_skills"]} <= {"extracted", "inferred"}


def test_every_skill_has_evidence():
    out = run_extraction("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), allow_external=False)
    assert all(s.get("evidence") for s in out.profile["tech_skills"])


def test_sensitive_values_never_kept():
    out = run_extraction("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), allow_external=False)
    blob = json.dumps(out.profile, ensure_ascii=False)
    assert "1.020.555.555" not in blob and "12/03/1994" not in blob


def test_rejects_bad_files():
    with pytest.raises(InvalidDocument):
        run_extraction("a.pdf", b"not a pdf", allow_external=False)
    with pytest.raises(InvalidDocument):
        run_extraction("a.png", b"GIF89a....", allow_external=False)
    with pytest.raises(InvalidDocument):
        run_extraction("a.json", b"{no json", allow_external=False)
    with pytest.raises(InvalidDocument):
        run_extraction("a.docx", b"PK\x03\x04", allow_external=False)


class FakeProvider:
    name, model = "anthropic", "modelo-de-prueba"

    def __init__(self, payload=None, fail=False):
        self.payload, self.fail, self.calls, self.last_text = payload, fail, 0, None

    def available(self):
        return True

    def call(self, text):
        self.calls += 1
        self.last_text = text
        if self.fail:
            raise RuntimeError("timeout")
        return "Respuesta:\n" + json.dumps(self.payload)


PAYLOAD = {
    "tecnicas": [{"nombre": "Kafka", "evidencia": "Python, SQL, Apache Spark, Apache Kafka"},   # literal -> aceptada
                 {"nombre": "Kubernetes", "evidencia": "Administré clústeres de Kubernetes"}],  # sin evidencia -> descartada
    "power_skills": [{"nombre": "Mentoría", "evidencia": "Capacité a 20 usuarios en visualización de datos"}],
    "certificaciones": [{"nombre": "Certificación inventada", "evidencia": "no aparece en el CV"}],
}


def test_external_provider_items_require_literal_evidence():
    fake = FakeProvider(PAYLOAD)
    out = run_extraction("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), allow_external=True, provider=fake)
    assert fake.calls == 1 and out.external_used and out.provider == "anthropic"
    assert out.stats["external_rejected"] == 2
    # se envió texto minimizado: sin correo ni teléfono ni documento
    assert "@" not in fake.last_text and "310 555" not in fake.last_text and "1.020.555" not in fake.last_text
    keys = {s["key"] for s in out.profile["tech_skills"]}
    assert "kubernetes" not in keys
    assert not any(c["title"] == "Certificación inventada" for c in out.profile.get("ai_certifications", []))


def test_external_provider_failure_falls_back_to_local():
    out = run_extraction("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), allow_external=True,
                         provider=FakeProvider(fail=True))
    assert out.provider == "local" and not out.external_used and "no respondió" in out.external_note
    assert out.profile["tech_skills"]


def test_external_not_called_without_authorization(monkeypatch):
    fake = FakeProvider(PAYLOAD)
    from app.modules.extraction import providers
    monkeypatch.setattr(providers, "select_provider", lambda *_: fake)
    run_extraction("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), allow_external=False)
    assert fake.calls == 0


def test_api_respects_employee_ai_choice(client, monkeypatch):
    """Sofía otorgó consentimiento SIN IA externa: aunque haya proveedor, no se usa."""
    from conftest import API, login
    fake = FakeProvider(PAYLOAD)
    from app.modules.extraction import providers
    monkeypatch.setattr(providers, "select_provider", lambda *_: fake)
    h = login(client, "valentina.ospina@talentmatch.demo", "EmpleadoDemo2026!")  # external_ai=True en la semilla
    r = client.post(f"{API}/profiles/me/cv", headers=h,
                    files={"file": ("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), "application/pdf")})
    assert r.status_code == 201 and fake.calls == 1 and r.json()["last_extraction"]["external_used"]
    fake.calls = 0
    h2 = login(client, "santiago.herrera@talentmatch.demo", "EmpleadoDemo2026!")  # external_ai=False
    client.post(f"{API}/profiles/me/cv", headers=h2,
                files={"file": ("cv.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes(), "application/pdf")})
    assert fake.calls == 0


def test_gemini_provider_contract(monkeypatch):
    from app.core.config import get_settings
    from pydantic import SecretStr
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", SecretStr("clave-falsa"))
    seen = {}

    def handler(request: httpx.Request):
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(PAYLOAD)}]}}]})

    prov = GeminiProvider(transport=httpx.MockTransport(handler))
    raw = prov.call("<texto>")
    assert seen["key"] == "clave-falsa" and seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    res = verify_items(parse_payload(raw), "Python, SQL, Apache Spark, Apache Kafka", "gemini", prov.model)
    assert [t["key"] for t in res.tech] == ["apache kafka"] and res.rejected == 3


def test_invalid_llm_json_is_rejected():
    with pytest.raises(ValueError):
        parse_payload('{"tecnicas": "no-es-lista"}')
    with pytest.raises(ValueError):
        parse_payload("sin json")


def test_networking_is_technical_not_interpersonal():
    """Regresión V6: It4 clasificaba 'Networking' (redes) como la power skill 'Relaciones interpersonales'."""
    from app.modules.catalog.skills import canonical_soft
    assert canonical_soft("Networking") is None
    assert canonical_soft("Networking skills") == "interpersonal"
