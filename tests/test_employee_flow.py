"""Flujo completo del empleado: consentimiento → CV → revisión → publicación → oportunidades (Sofía, demo en vivo)."""
from conftest import API
from helpers import pdf_with_text

from app.core.config import BASE_DIR
from app.core.config import get_settings

LIVE_CV = BASE_DIR / "demo" / "cvs" / "cv_demo_sofia_arango.pdf"


def _policy_version():
    return get_settings().consent_policy_version


def test_upload_requires_consent(client, live_h):
    r = client.post(f"{API}/profiles/me/cv", headers=live_h,
                    files={"file": ("cv.pdf", LIVE_CV.read_bytes(), "application/pdf")})
    assert r.status_code == 403


def test_consent_requires_current_policy(client, live_h):
    r = client.post(f"{API}/consent/me", headers=live_h, json={"processing": True, "policy_version": "vieja"})
    assert r.status_code == 409


def test_live_flow(client, live_h, hr_h):
    r = client.post(f"{API}/consent/me", headers=live_h,
                    json={"processing": True, "external_ai": False, "policy_version": _policy_version()})
    assert r.status_code == 200 and r.json()["processing"] is True

    up = client.post(f"{API}/profiles/me/cv", headers=live_h,
                     files={"file": ("cv_sofia.pdf", LIVE_CV.read_bytes(), "application/pdf")})
    assert up.status_code == 201, up.text
    prof = up.json()
    ex = prof["last_extraction"]
    assert ex["provider"] == "local" and ex["external_used"] is False
    # datos sensibles detectados y descartados (solo categorías)
    assert "Fecha de nacimiento" in ex["sensitive_categories"] and "Estado civil" in ex["sensitive_categories"]
    assert all("1998" not in (s["evidence"] or "") for s in prof["skills"])
    names = {s["name"] for s in prof["skills"]}
    assert {"Python", "SQL", "FastAPI"} <= names
    # transparencia: todo llega pendiente y con origen
    assert all(s["status"] == "pending" for s in prof["skills"])
    assert {s["origin"] for s in prof["skills"]} <= {"extracted", "inferred", "ai_external"}
    assert prof["years_experience"] > 0 and prof["years_source"] == "extracted"

    # no se puede publicar sin confirmar
    assert client.post(f"{API}/profiles/me/publish", headers=live_h).status_code == 409
    # RR. HH. no ve el borrador
    hr_ids = {c["profile_id"] for c in client.get(f"{API}/talent", headers=hr_h).json()}
    assert prof["id"] not in hr_ids

    # corregir: rechazar una, confirmar otra, agregar una manual
    py = next(s for s in prof["skills"] if s["name"] == "Python")
    some = next(s for s in prof["skills"] if s["name"] not in ("Python", "SQL", "FastAPI"))
    client.patch(f"{API}/profiles/me/skills/{some['id']}", headers=live_h, json={"status": "rejected"})
    client.patch(f"{API}/profiles/me/skills/{py['id']}", headers=live_h, json={"status": "confirmed", "level": 4})
    m = client.post(f"{API}/profiles/me/skills", headers=live_h, json={"kind": "tech", "name": "Apache Airflow", "level": 2})
    assert m.status_code == 201
    manual = next(s for s in m.json()["skills"] if s["name"] == "Apache Airflow")
    assert manual["origin"] == "manual" and manual["status"] == "confirmed"

    conf = client.post(f"{API}/profiles/me/confirm-all", headers=live_h, json={"min_confidence": 0.8}).json()
    rejected = next(s for s in conf["skills"] if s["id"] == some["id"])
    assert rejected["status"] == "rejected"  # confirmar todo no revive lo rechazado
    pub = client.post(f"{API}/profiles/me/publish", headers=live_h)
    assert pub.status_code == 200 and pub.json()["status"] == "published"

    # RR. HH. ve solo lo confirmado y sin correo
    view = client.get(f"{API}/talent/{prof['id']}", headers=hr_h).json()
    assert view["email"] is None
    assert all(s["status"] == "confirmed" for s in view["skills"])
    assert all(s["name"] != rejected["name"] for s in view["skills"])

    # oportunidades del empleado con desglose
    opps = client.get(f"{API}/opportunities", headers=live_h).json()["items"]
    assert opps and "components" in opps[0] and "explanation" in opps[0]
    det = client.get(f"{API}/opportunities/{opps[0]['position_id']}", headers=live_h).json()
    assert "recommendations" in det

    # reprocesar el CV conserva lo confirmado y lo rechazado
    again = client.post(f"{API}/profiles/me/cv", headers=live_h,
                        files={"file": ("cv_sofia.pdf", LIVE_CV.read_bytes(), "application/pdf")}).json()
    assert any(s["name"] == "Apache Airflow" and s["status"] == "confirmed" for s in again["skills"])
    assert any(s["id"] == some["id"] and s["status"] == "rejected" for s in again["skills"])


def test_revoking_consent_unpublishes(client, live_h, hr_h):
    me = client.get(f"{API}/profiles/me", headers=live_h).json()
    assert me["status"] == "published"
    client.post(f"{API}/consent/me", headers=live_h, json={"processing": False, "policy_version": _policy_version()})
    me = client.get(f"{API}/profiles/me", headers=live_h).json()
    assert me["status"] == "draft"
    assert client.get(f"{API}/talent/{me['id']}", headers=hr_h).status_code == 404
    hist = client.get(f"{API}/consent/me/history", headers=live_h).json()
    assert len(hist) >= 2 and hist[0]["processing"] is False
    # se restablece para el resto de pruebas
    client.post(f"{API}/consent/me", headers=live_h, json={"processing": True, "policy_version": _policy_version()})
    client.post(f"{API}/profiles/me/publish", headers=live_h)


def test_upload_validation(client, emp_h):
    bad = client.post(f"{API}/profiles/me/cv", headers=emp_h, files={"file": ("cv.pdf", b"MZ\x90 malware", "application/pdf")})
    assert bad.status_code == 415
    ext = client.post(f"{API}/profiles/me/cv", headers=emp_h, files={"file": ("cv.exe", b"%PDF-1.4", "application/pdf")})
    assert ext.status_code == 415
    s = get_settings()
    big = b"%PDF-1.4\n" + b"0" * (s.max_upload_mb * 1024 * 1024 + 10)
    assert client.post(f"{API}/profiles/me/cv", headers=emp_h, files={"file": ("cv.pdf", big, "application/pdf")}).status_code == 413
    empty_text = pdf_with_text("Hola")
    assert client.post(f"{API}/profiles/me/cv", headers=emp_h,
                       files={"file": ("cv.pdf", empty_text, "application/pdf")}).status_code == 422


def test_export_contains_own_data_only(client, emp_h):
    r = client.get(f"{API}/profiles/me/export", headers=emp_h)
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    data = r.json()
    assert data["profile"]["full_name"] == "Valentina Ospina Rueda"
    assert "no se almacena" in data["note"]
