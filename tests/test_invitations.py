from conftest import API, login


def test_hr_can_only_invite_employees(client, hr_h):
    r = client.post(f"{API}/invitations", headers=hr_h, json={"email": "nuevo.admin@talentmatch.demo",
                                                              "full_name": "Intento Admin", "role": "admin"})
    assert r.status_code == 403


def test_full_invitation_flow(client, hr_h):
    r = client.post(f"{API}/invitations", headers=hr_h, json={"email": "ana.prueba@talentmatch.demo",
                                                              "full_name": "Ana Prueba Ficticia", "role": "employee",
                                                              "department": "Tecnología"})
    assert r.status_code == 201, r.text
    url = r.json()["invite_url"]
    token = url.rsplit("/", 1)[1]
    # vista previa pública: correo enmascarado
    pv = client.get(f"{API}/invitations/token/{token}").json()
    assert pv["email_masked"].startswith("an") and "•" in pv["email_masked"]
    # contraseña débil rechazada
    assert client.post(f"{API}/invitations/token/{token}/accept", json={"password": "debilsinnumero"}).status_code == 422
    ok = client.post(f"{API}/invitations/token/{token}/accept", json={"password": "ClaveNueva2026segura"})
    assert ok.status_code == 201
    # un solo uso
    assert client.post(f"{API}/invitations/token/{token}/accept", json={"password": "ClaveNueva2026segura"}).status_code == 410
    h = login(client, "ana.prueba@talentmatch.demo", "ClaveNueva2026segura")
    me = client.get(f"{API}/auth/me", headers=h).json()
    assert me["role"] == "employee" and me["department"] == "Tecnología"
    # la invitación figura como aceptada
    invs = client.get(f"{API}/invitations", headers=hr_h).json()
    assert any(i["email"] == "ana.prueba@talentmatch.demo" and i["status"] == "accepted" for i in invs)


def test_duplicate_email_rejected(client, hr_h):
    r = client.post(f"{API}/invitations", headers=hr_h, json={"email": "valentina.ospina@talentmatch.demo",
                                                              "full_name": "Duplicada", "role": "employee"})
    assert r.status_code == 409


def test_unknown_token_404(client):
    assert client.get(f"{API}/invitations/token/no-existe").status_code == 404
