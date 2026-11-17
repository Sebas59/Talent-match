from sqlmodel import Session, func, select

from conftest import API

from app.core.database import engine
from app.modules.profiles.models import Profile
from app.modules.projects.models import Position


def test_overview_matches_database(client, hr_h):
    ov = client.get(f"{API}/analytics/overview", headers=hr_h).json()
    with Session(engine) as s:
        published = s.exec(select(func.count()).select_from(Profile).where(Profile.status == "published")).one()
        open_pos = s.exec(select(func.count()).select_from(Position).where(Position.status == "open")).one()
    assert ov["published_profiles"] <= published and ov["published_profiles"] > 0
    assert ov["open_positions"] == open_pos


def test_skills_report_supply_demand(client, hr_h):
    rep = client.get(f"{API}/analytics/skills", headers=hr_h).json()
    assert rep["top"] and rep["gaps"]
    kafka = next((g for g in rep["gaps"] if g["key"] == "apache kafka"), None)
    assert kafka and kafka["supply"] == 0 and kafka["status"] == "crítica"
    filt = client.get(f"{API}/analytics/skills", headers=hr_h, params={"kind": "power"}).json()
    assert all(t["kind"] == "power" for t in filt["top"])


def test_positions_and_training_reports(client, hr_h):
    pos = client.get(f"{API}/analytics/positions", headers=hr_h).json()
    assert pos and all("available" in p for p in pos)
    tr = client.get(f"{API}/analytics/training", headers=hr_h).json()
    assert tr["paths"] >= 4 and tr["needs"]


def test_governance_card_and_metrics(client, emp_h, hr_h):
    card = client.get(f"{API}/governance/card", headers=emp_h).json()
    assert len(card["items"]) == 10 and "deciden" in card["principle"]
    m = client.get(f"{API}/governance/metrics", headers=hr_h).json()
    assert m["automatic_decisions"] == 0 and m["human_decisions"] >= 4
    assert m["sensitive_discarded"].get("Fecha de nacimiento", 0) >= 1


def test_extraction_benchmark(client, hr_h):
    b = client.get(f"{API}/governance/benchmark", headers=hr_h).json()
    assert b["available"] and b["recall_tecnica"] >= 85 and b["sensibles_ok"] == b["n"]
