"""Matriz de permisos verificada en el servidor (no solo ocultando botones)."""
import pytest

from conftest import API

HR_ONLY = [("get", "/talent"), ("get", "/projects"), ("get", "/positions"), ("get", "/analytics/overview"),
           ("get", "/development/paths"), ("get", "/decisions")]
ADMIN_ONLY = [("get", "/admin/users"), ("get", "/admin/settings"), ("get", "/audit"), ("get", "/audit/verify"),
              ("get", "/privacy/requests"), ("get", "/admin/system")]
EMPLOYEE_ONLY = [("get", "/profiles/me"), ("get", "/opportunities"), ("get", "/development/me"),
                 ("get", "/privacy/requests/me")]


@pytest.mark.parametrize("method,path", HR_ONLY)
def test_hr_routes_forbidden_for_employee_and_admin(client, emp_h, admin_h, hr_h, method, path):
    assert getattr(client, method)(API + path, headers=emp_h).status_code == 403
    assert getattr(client, method)(API + path, headers=admin_h).status_code == 403
    assert getattr(client, method)(API + path, headers=hr_h).status_code == 200


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_admin_routes_forbidden_for_hr_and_employee(client, emp_h, admin_h, hr_h, method, path):
    assert getattr(client, method)(API + path, headers=emp_h).status_code == 403
    assert getattr(client, method)(API + path, headers=hr_h).status_code == 403
    assert getattr(client, method)(API + path, headers=admin_h).status_code == 200


@pytest.mark.parametrize("method,path", EMPLOYEE_ONLY)
def test_employee_routes_forbidden_for_staff(client, emp_h, admin_h, hr_h, method, path):
    assert getattr(client, method)(API + path, headers=hr_h).status_code == 403
    assert getattr(client, method)(API + path, headers=admin_h).status_code == 403
    assert getattr(client, method)(API + path, headers=emp_h).status_code == 200


def test_admin_cannot_read_profile_content(client, admin_h, hr_h):
    pid = client.get(f"{API}/talent", headers=hr_h).json()[0]["profile_id"]
    assert client.get(f"{API}/talent/{pid}", headers=admin_h).status_code == 403
    users = client.get(f"{API}/admin/users", headers=admin_h).json()
    assert all("skills" not in u and "summary" not in u for u in users)


def test_forbidden_attempts_are_audited(client, emp_h, admin_h):
    client.get(f"{API}/admin/users", headers=emp_h)
    ev = client.get(f"{API}/audit", headers=admin_h, params={"action": "forbidden"}).json()
    assert ev and ev[0]["category"] == "security"


def test_dashboard_is_role_specific(client, emp_h, hr_h, admin_h):
    assert client.get(f"{API}/dashboard", headers=emp_h).json()["role"] == "employee"
    assert client.get(f"{API}/dashboard", headers=hr_h).json()["role"] == "hr"
    d = client.get(f"{API}/dashboard", headers=admin_h).json()
    assert d["role"] == "admin" and "users_by_role" in d


def test_hr_cannot_change_roles(client, hr_h, admin_h):
    uid = client.get(f"{API}/admin/users", headers=admin_h).json()[-1]["id"]
    assert client.patch(f"{API}/admin/users/{uid}", headers=hr_h, json={"role": "admin"}).status_code == 403
