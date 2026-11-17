"""Control de propiedad: un empleado nunca puede operar sobre recursos de otro."""
from conftest import API


def _first_skill(client, h):
    return client.get(f"{API}/profiles/me", headers=h).json()["skills"][0]


def test_employee_cannot_modify_other_skill(client, emp_h, emp2_h):
    other = _first_skill(client, emp2_h)
    r = client.patch(f"{API}/profiles/me/skills/{other['id']}", headers=emp_h, json={"status": "rejected"})
    assert r.status_code == 404
    assert client.delete(f"{API}/profiles/me/skills/{other['id']}", headers=emp_h).status_code == 404
    still = client.get(f"{API}/profiles/me", headers=emp2_h).json()["skills"]
    assert any(s["id"] == other["id"] and s["status"] == other["status"] for s in still)


def test_employee_cannot_modify_other_entry(client, emp_h, emp2_h):
    other = client.get(f"{API}/profiles/me", headers=emp2_h).json()["entries"][0]
    assert client.patch(f"{API}/profiles/me/entries/{other['id']}", headers=emp_h, json={"status": "rejected"}).status_code == 404


def test_employee_cannot_update_other_learning_item(client, hr_h, emp_h):
    paths = client.get(f"{API}/development/paths", headers=hr_h).json()
    foreign = next(p for p in paths if p["full_name"] != "Valentina Ospina Rueda")
    item = foreign["items"][0]["id"]
    assert client.patch(f"{API}/development/items/{item}", headers=emp_h, json={"progress": 100}).status_code == 404


def test_employee_only_sees_own_opportunity_scores(client, emp_h):
    data = client.get(f"{API}/opportunities", headers=emp_h).json()
    for o in data["items"]:
        assert "full_name" not in o and "results" not in o


def test_hr_cannot_see_unpublished_profile(client, hr_h):
    cards = client.get(f"{API}/talent", headers=hr_h).json()
    assert all(c["full_name"] != "Isabela Moreno Duarte" for c in cards)  # borrador en la semilla
