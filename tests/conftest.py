"""Entorno de pruebas aislado (base temporal, sin claves de IA). Basado en el conftest de V5."""
import os
import tempfile

from cryptography.fernet import Fernet

_tmp = tempfile.mkdtemp()
os.environ.update({
    "ENVIRONMENT": "test",
    "SECRET_KEY": "t" * 64,
    "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "BLIND_INDEX_KEY": "b" * 64,
    "ADMIN_EMAIL": "",
    "ADMIN_PASSWORD": "",
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "ALLOWED_HOSTS": '["testserver"]',
    "ANTHROPIC_API_KEY": "",
    "GEMINI_API_KEY": "",
    "AI_PROVIDER": "auto",
    "LOGIN_MAX_ATTEMPTS": "3",
    "RATE_LIMIT_PER_MINUTE": "60000",
    "WARM_CATALOG_ON_START": "false",
    "DEMO_MODE": "true",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from scripts import demo_data as D  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        from scripts.seed_demo import seed
        seed(reset=True, quiet=True)
        yield c


def login(client, email, password):
    r = client.post(f"{API}/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_h(client):
    return login(client, D.ADMIN["email"], D.ADMIN["password"])


@pytest.fixture(scope="session")
def hr_h(client):
    return login(client, D.HR_USERS[0]["email"], D.HR_USERS[0]["password"])


@pytest.fixture(scope="session")
def emp_h(client):
    return login(client, f"valentina.ospina@{D.ORG_DOMAIN}", D.EMPLOYEE_PASSWORD)


@pytest.fixture(scope="session")
def emp2_h(client):
    return login(client, f"santiago.herrera@{D.ORG_DOMAIN}", D.EMPLOYEE_PASSWORD)


@pytest.fixture(scope="session")
def live_h(client):
    return login(client, f"sofia.arango@{D.ORG_DOMAIN}", D.EMPLOYEE_PASSWORD)
