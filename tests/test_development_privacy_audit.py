from conftest import API


def test_hr_assigns_path_from_match_and_employee_progress(client, hr_h, emp2_h):
    runs = client.get(f"{API}/positions", headers=hr_h).json()
    pos = next(p for p in runs if p["title"].startswith("Ingeniero(a) de Datos"))
    run = client.get(f"{API}/positions/{pos['id']}/latest-run", headers=hr_h).json()
    santi = next(r for r in run["results"] if r["full_name"] == "Santiago Herrera Pardo")
    lp = client.post(f"{API}/development/paths", headers=hr_h, json={
        "profile_id": santi["profile_id"], "title": "Ruta datos para Santiago", "position_id": pos["id"],
        "match_result_id": santi["id"], "due_date": "2027-06-30"})
    assert lp.status_code == 201, lp.text
    path = lp.json()
    assert path["items"] and path["assigned_by"] == "Carolina Beltrán Ruiz"
    # cada ítem nace de una brecha del matching
    gap_names = {g["name"] for g in santi["gaps"]}
    assert {i["skill"] for i in path["items"]} <= gap_names
    mine = client.get(f"{API}/development/me", headers=emp2_h).json()
    target = next(p for p in mine if p["id"] == path["id"])
    item = target["items"][0]["id"]
    upd = client.patch(f"{API}/development/items/{item}", headers=emp2_h, json={"progress": 100}).json()
    assert next(i for i in upd["items"] if i["id"] == item)["status"] == "completed" and upd["progress"] > 0


def test_recommendations_are_justified_by_gaps(client, emp2_h):
    rec = client.get(f"{API}/development/me/recommendations", headers=emp2_h).json()
    assert rec["position"] and "datasets" in rec["catalog_note"]
    for r in rec["recommendations"]:
        assert r["skill"]
        for c in r["courses"]:
            assert c["url"].startswith("https://") and c["rating"] > 4.0


def test_privacy_request_lifecycle_and_execution(client, admin_h):
    from conftest import login
    h = login(client, "paula.rios@talentmatch.demo", "EmpleadoDemo2026!")
    r = client.post(f"{API}/privacy/requests", headers=h, json={"type": "deletion", "detail": "Deseo suprimir mi perfil."})
    assert r.status_code == 201
    rid = r.json()["id"]
    lst = client.get(f"{API}/privacy/requests", headers=admin_h, params={"status": "open"}).json()
    assert any(x["id"] == rid and x["requester"] == "Paula Andrea Ríos Salazar" for x in lst)
    res = client.patch(f"{API}/privacy/requests/{rid}", headers=admin_h,
                       json={"status": "resolved", "resolution": "Datos suprimidos según solicitud.", "execute": True})
    assert res.status_code == 200 and res.json()["status"] == "resolved"
    prof = client.get(f"{API}/profiles/me", headers=h).json()
    assert prof["skills"] == [] and prof["status"] == "draft"
    assert client.get(f"{API}/consent/me", headers=h).json()["processing"] is False


def test_employee_can_wipe_own_data(client):
    from conftest import login
    h = login(client, "isabela.moreno@talentmatch.demo", "EmpleadoDemo2026!")
    r = client.delete(f"{API}/profiles/me/data", headers=h)
    assert r.status_code == 200 and r.json()["skills"] == [] and r.json()["entries"] == []


def test_audit_chain_valid_and_detects_tampering(client, admin_h):
    v = client.get(f"{API}/audit/verify", headers=admin_h).json()
    assert v["valid"] and v["checked"] > 20
    from sqlmodel import Session, select

    from app.core.database import engine
    from app.modules.audit.models import AuditLog
    from app.modules.audit.service import verify_chain
    with Session(engine) as s:
        row = s.exec(select(AuditLog).where(AuditLog.id == 5)).first()
        original = row.detail
        row.detail = "alterado"
        s.add(row)
        s.commit()
        broken = verify_chain(s)
        assert not broken["valid"] and broken["broken_at"] == 5
        row.detail = original
        s.add(row)
        s.commit()
        assert verify_chain(s)["valid"]


def test_audit_has_no_personal_data(client, admin_h):
    rows = client.get(f"{API}/audit", headers=admin_h, params={"limit": 500}).json()
    blob = " ".join(str(r.get("detail") or "") for r in rows)
    assert "@" not in blob and "Valentina" not in blob


def test_settings_validation_and_effect(client, admin_h, emp_h):
    bad = client.put(f"{API}/admin/settings", headers=admin_h, json={"values": {"availability_threshold": 500}})
    assert bad.status_code == 422
    ok = client.put(f"{API}/admin/settings", headers=admin_h,
                    json={"values": {"default_weights": {"technical": 2, "power": 1, "experience": 1, "credentials": 0}}})
    w = ok.json()["values"]["default_weights"]
    assert abs(sum(w.values()) - 1) < 1e-3 and w["technical"] == 0.5


def test_admin_role_change_revokes_sessions(client, admin_h):
    from conftest import login
    h = login(client, "camilo.vega@talentmatch.demo", "EmpleadoDemo2026!")
    uid = client.get(f"{API}/auth/me", headers=h).json()["id"]
    assert client.patch(f"{API}/admin/users/{uid}", headers=admin_h, json={"is_active": False}).status_code == 200
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401
    client.patch(f"{API}/admin/users/{uid}", headers=admin_h, json={"is_active": True})


def test_admin_cannot_demote_self(client, admin_h):
    me = client.get(f"{API}/auth/me", headers=admin_h).json()
    assert client.patch(f"{API}/admin/users/{me['id']}", headers=admin_h, json={"role": "hr"}).status_code == 409
