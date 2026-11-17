"""Proyectos, requisitos, matching explicable, persistencia y decisiones humanas."""
from conftest import API

from app.modules.matching.engine import Candidate, PositionSpec, Requirement, evaluate, normalize_weights


def test_engine_weights_and_redistribution():
    spec = PositionSpec(requirements=[Requirement("tech", "python", "Python", "mandatory"),
                                      Requirement("power", "teamwork", "Trabajo en equipo")],
                        weights={"technical": 40, "power": 25, "experience": 20, "credentials": 15})
    r = evaluate(Candidate(tech={"python": {"name": "Python"}}, power={"teamwork": {"name": "Trabajo en equipo"}}), spec)
    assert r["score"] == 100.0 and r["eligible"]
    assert r["components"]["experience"]["applicable"] is False
    assert abs(sum(c["effective_weight"] for c in r["components"].values()) - 1) < 1e-3
    assert normalize_weights({"technical": 0, "power": 0, "experience": 0, "credentials": 0})["technical"] == 0.25


def test_engine_mandatory_and_related_credit():
    spec = PositionSpec(requirements=[Requirement("tech", "ci/cd", "CI/CD", "mandatory"),
                                      Requirement("tech", "docker", "Docker")], weights={"technical": 1})
    r = evaluate(Candidate(tech={"git": {"name": "Git"}, "docker": {"name": "Docker"}}), spec)
    req = next(x for x in r["requirements"] if x["key"] == "ci/cd")
    assert req["credit"] == 0.6 and req["match_type"] == "relacionada"
    assert r["eligible"] is False and "CI/CD" in r["mandatory_unmet"]
    assert 0 < r["score"] < 100


def test_engine_experience_and_certifications():
    spec = PositionSpec(requirements=[Requirement("tech", "aws", "AWS"),
                                      Requirement("certification", "aws certified solutions architect",
                                                  "AWS Certified Solutions Architect")],
                        weights={"technical": .5, "experience": .25, "credentials": .25}, min_years=4,
                        min_years_mandatory=True)
    c = Candidate(tech={"aws": {"name": "AWS"}}, certifications=["AWS Certified Solutions Architect - Associate (2023)"],
                  years=2)
    r = evaluate(c, spec)
    assert r["components"]["experience"]["value"] == 50.0
    assert r["components"]["credentials"]["value"] == 100.0
    assert not r["eligible"] and any("Experiencia mínima" in x for x in r["mandatory_unmet"])


def test_create_project_position_and_run_match(client, hr_h):
    p = client.post(f"{API}/projects", headers=hr_h, json={"name": "Proyecto de Prueba QA", "area": "Pruebas",
                                                           "status": "active"})
    assert p.status_code == 201
    pid = p.json()["id"]
    bad = client.post(f"{API}/projects/{pid}/positions", headers=hr_h, json={
        "title": "Cargo inválido", "weights": {"technical": 0, "power": 0, "experience": 0, "credentials": 0}})
    assert bad.status_code == 422
    pos = client.post(f"{API}/projects/{pid}/positions", headers=hr_h, json={
        "title": "Ingeniero(a) de Datos Junior", "min_years": 2, "education_level": 4,
        "weights": {"technical": 0.5, "power": 0.2, "experience": 0.2, "credentials": 0.1},
        "requirements": [{"kind": "tech", "name": "Python", "importance": "mandatory"},
                         {"kind": "tech", "name": "postgres", "importance": "desirable"},
                         {"kind": "power", "name": "trabajo en equipo"},
                         {"kind": "certification", "name": "AWS Certified Data Engineer"}]})
    assert pos.status_code == 201, pos.text
    body = pos.json()
    assert abs(sum(body["weights"].values()) - 1) < 1e-3
    names = {r["name"] for r in body["requirements"]}
    assert "PostgreSQL" in names and "Trabajo en equipo" in names  # canonización ES↔EN y sinónimos

    run = client.post(f"{API}/positions/{body['id']}/match", headers=hr_h, json={})
    assert run.status_code == 200
    data = run.json()
    assert data["evaluated"] >= 10 and data["results"]
    top = data["results"][0]
    assert top["full_name"] == "Valentina Ospina Rueda" and top["eligible"]
    for k in ("components", "matched", "missing", "gaps", "strengths", "evidence", "explanation"):
        assert k in top
    # ordenado: elegibles primero y por puntaje
    elig = [r["eligible"] for r in data["results"]]
    assert elig == sorted(elig, reverse=True)
    # persistido
    again = client.get(f"{API}/positions/{body['id']}/latest-run", headers=hr_h).json()
    assert again["id"] == data["id"] and len(again["results"]) == len(data["results"])

    # pesos ad hoc en la ejecución
    alt = client.post(f"{API}/positions/{body['id']}/match", headers=hr_h,
                      json={"weights": {"technical": 0.1, "power": 0.8, "experience": 0.05, "credentials": 0.05}}).json()
    assert alt["weights"]["power"] == 0.8 and alt["id"] != data["id"]

    # decisión humana: justificación obligatoria
    short = client.post(f"{API}/positions/{body['id']}/decisions", headers=hr_h,
                        json={"profile_id": top["profile_id"], "decision": "shortlisted", "justification": "ok"})
    assert short.status_code == 422
    d = client.post(f"{API}/positions/{body['id']}/decisions", headers=hr_h, json={
        "profile_id": top["profile_id"], "decision": "shortlisted", "match_result_id": top["id"],
        "justification": "Cumple los obligatorios y tiene experiencia en pipelines similares."})
    assert d.status_code == 201 and d.json()["score_at_decision"] == top["score"]
    latest = client.get(f"{API}/positions/{body['id']}/latest-run", headers=hr_h).json()
    assert latest["results"][0]["decision"]["decision"] == "shortlisted"


def test_decision_visible_to_employee(client, emp_h):
    procs = client.get(f"{API}/opportunities/processes", headers=emp_h).json()
    assert any(p["decision"] == "interview" for p in procs)  # registrada en la semilla


def test_template_search_and_detail(client, hr_h):
    r = client.post(f"{API}/catalog/job-templates/search", headers=hr_h, json={"query": "data engineer", "limit": 3})
    items = r.json()["items"]
    assert items and items[0]["tech"]
    det = client.get(f"{API}/catalog/job-templates/{items[0]['job_id']}", headers=hr_h).json()
    assert det["requirements"]


def test_skill_autocomplete(client, emp_h):
    assert any(s["name"] == "Python" for s in client.get(f"{API}/catalog/skills", headers=emp_h, params={"q": "pyth"}).json())
    soft = client.get(f"{API}/catalog/skills", headers=emp_h, params={"q": "lider", "kind": "power"}).json()
    assert any(s["key"] == "leadership" for s in soft)
