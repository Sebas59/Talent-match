"""Autenticación y seguridad (pruebas de V5 adaptadas + revocación de sesiones de V6)."""
import jwt

from conftest import API, login
from scripts import demo_data as D


def test_health_and_security_headers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    csp = r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp


def test_api_responses_are_not_cached(client, hr_h):
    assert client.get(f"{API}/auth/me", headers=hr_h).headers["Cache-Control"] == "no-store"


def test_protected_requires_token(client):
    assert client.get(f"{API}/talent").status_code == 401
    assert client.get(f"{API}/talent", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_alg_none_rejected(client):
    forged = jwt.encode({"sub": "x", "sid": "y"}, key=None, algorithm="none")
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_me_does_not_leak_hash(client, hr_h):
    body = client.get(f"{API}/auth/me", headers=hr_h).json()
    assert "hashed_password" not in body and body["role"] == "hr"


def test_untrusted_host_rejected(client):
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400


def test_email_and_name_encrypted_at_rest(client):
    from sqlmodel import Session, select

    from app.core.database import engine
    from app.modules.auth.models import User
    with Session(engine) as s:
        u = s.exec(select(User)).first()
        assert "@" not in u.email_enc and u.email_enc.startswith("gAAAA")
        assert len(u.email_index) == 64


def test_logout_revokes_token_server_side(client):
    h = login(client, D.HR_USERS[1]["email"], D.HR_USERS[1]["password"])
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=h).status_code == 204
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401  # el JWT aún no expira, pero la sesión sí


def test_refresh_rotation_and_reuse_detection(client):
    r = client.post(f"{API}/auth/token", data={"username": D.HR_USERS[1]["email"], "password": D.HR_USERS[1]["password"]})
    old = r.cookies.get("tm_refresh") or client.cookies.get("tm_refresh")
    assert old
    # sin la cabecera propia (protección CSRF) se rechaza
    assert client.post(f"{API}/auth/refresh").status_code == 401
    client.cookies.set("tm_refresh", old, path="/api/v1/auth")
    r2 = client.post(f"{API}/auth/refresh", headers={"X-TM-Refresh": "1"})
    assert r2.status_code == 200 and r2.json()["access_token"]
    # reutilizar el refresh anterior revoca la sesión completa
    client.cookies.clear()
    client.cookies.set("tm_refresh", old, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh", headers={"X-TM-Refresh": "1"}).status_code == 401
    new_access = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=new_access).status_code == 401
    client.cookies.clear()


def test_lockout_after_failed_logins(client):
    email = f"natalia.suarez@{D.ORG_DOMAIN}"
    for _ in range(3):
        client.post(f"{API}/auth/token", data={"username": email, "password": "mala-clave-123"})
    r = client.post(f"{API}/auth/token", data={"username": email, "password": D.EMPLOYEE_PASSWORD})
    assert r.status_code == 401  # bloqueada aunque la clave sea correcta


def test_admin_can_unlock(client, admin_h):
    users = client.get(f"{API}/admin/users", headers=admin_h, params={"q": "natalia"}).json()
    uid = users[0]["id"]
    assert client.post(f"{API}/admin/users/{uid}/unlock", headers=admin_h).status_code == 200
    login(client, f"natalia.suarez@{D.ORG_DOMAIN}", D.EMPLOYEE_PASSWORD)


def test_weak_password_rejected_on_change(client):
    h = login(client, f"felipe.ramirez@{D.ORG_DOMAIN}", D.EMPLOYEE_PASSWORD)
    r = client.post(f"{API}/auth/password", headers=h, json={"current_password": D.EMPLOYEE_PASSWORD,
                                                             "new_password": "solo-letras-sin-numero"})
    assert r.status_code == 422


def test_rate_limit_returns_429(client):
    from app.core.config import get_settings
    s = get_settings()
    old = s.rate_limit_per_minute
    s.rate_limit_per_minute = 3
    try:
        codes = [client.get(f"{API}/consent/policy").status_code for _ in range(5)]
    finally:
        s.rate_limit_per_minute = old
    assert 429 in codes
