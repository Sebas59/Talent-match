"""Evaluación reproducible del motor de matching (no requiere base de datos ni claves).

1. Precisión de ranking frente a una referencia esperada: para cada cargo demo se define qué perfil
   sintético debería quedar primero (su "titular natural"). Métricas: acierto top-1, top-3 y MRR.
2. Propiedades verificables del motor:
   - pesos normalizados suman 1 y los componentes no aplicables se redistribuyen;
   - monotonía: agregar una competencia exigida nunca baja el puntaje;
   - equivalencia de idioma: "Trabajo en equipo" y "Teamwork" puntúan igual;
   - un obligatorio sin cubrir quita la elegibilidad;
   - invariancia: el motor no recibe nombre, género, edad ni departamento (el contrato no los incluye).
3. Sensibilidad: estabilidad del ranking (tau de Kendall) al variar los pesos ±10 puntos.

Uso:  python -m scripts.evaluate_matching        (escribe docs/reports/evaluacion_matching.json)
"""
from __future__ import annotations

import json
import time
from dataclasses import fields
from itertools import combinations

from app.core.config import BASE_DIR
from app.modules.matching.engine import Candidate, PositionSpec, Requirement, evaluate, normalize_weights
from app.modules.projects.service import requirement_key
from scripts import demo_data as D
from scripts.seed_demo import cv_text, make_pdf

EXPECTED = {
    "Desarrollador(a) Backend Java": "santiago.herrera",
    "Desarrollador(a) Frontend React": "mariana.cardenas",
    "Analista de Pruebas Automatizadas": "camilo.vega",
    "Ingeniero(a) de Datos": "valentina.ospina",
    "Analista de Inteligencia de Negocio": "julian.restrepo",
    "Ingeniero(a) Cloud": "andres.galeano",
    "Ingeniero(a) DevOps": "tomas.quintero",
    "Científico(a) de Datos": "laura.pineda",
    "Ingeniero(a) de MLOps": "felipe.ramirez",
    "Líder de Proyecto Ágil": "daniela.torres",
}


def candidate_from_cv(spec: dict) -> Candidate:
    """Simula el flujo real: extracción local + confirmación de lo de confianza ≥ 0,75 (como en la semilla)."""
    from app.modules.extraction.service import run_extraction

    out = run_extraction("cv.pdf", make_pdf(cv_text(spec)), allow_external=False)
    p = out.profile
    keep = lambda xs: {x["key"]: {"name": x["name"], "evidence": x.get("evidence"), "origin": x["origin"]}  # noqa: E731
                       for x in xs if (x.get("confidence") or 0) >= 0.75}
    certs = [c if isinstance(c, str) else c.get("title", "") for c in p.get("certifications", [])]
    return Candidate(tech=keep(p["tech_skills"]), power=keep(p["soft_skills"]), certifications=certs,
                     years=float(p.get("years_experience") or 0), edu_level=int(p.get("education_level") or 0))


def spec_from_demo(ps: dict, weights: dict | None = None) -> PositionSpec:
    from app.modules.admin.settings import DEFAULT_WEIGHTS

    reqs = []
    for kind, name, imp in ps["requirements"]:
        key, label = requirement_key(kind, name)
        reqs.append(Requirement(kind=kind, key=key, name=label, importance=imp))
    return PositionSpec(requirements=reqs, weights=normalize_weights(weights or ps.get("weights") or DEFAULT_WEIGHTS),
                        min_years=ps.get("min_years", 0), min_years_mandatory=ps.get("min_years_mandatory", False),
                        education_level=ps.get("education_level", 0))


def ranking(cands: dict[str, Candidate], spec: PositionSpec) -> list[tuple[str, dict]]:
    scored = [(slug, evaluate(c, spec)) for slug, c in cands.items()]
    scored.sort(key=lambda x: (not x[1]["eligible"], -x[1]["score"]))
    return scored


def kendall_tau(a: list[str], b: list[str]) -> float:
    pos = {x: i for i, x in enumerate(b)}
    items = [x for x in a if x in pos]
    conc = disc = 0
    for x, y in combinations(items, 2):
        s = (items.index(x) - items.index(y)) * (pos[x] - pos[y])
        conc += s > 0
        disc += s < 0
    n = conc + disc
    return round((conc - disc) / n, 3) if n else 1.0


def properties() -> list[dict]:
    checks = []
    w = normalize_weights({"technical": 4, "power": 2, "experience": 2, "credentials": 2})
    checks.append({"check": "Pesos normalizados suman 1", "ok": abs(sum(w.values()) - 1) < 1e-3, "value": w})

    base_reqs = [Requirement("tech", "python", "Python", "mandatory"), Requirement("tech", "sql", "SQL"),
                 Requirement("power", "teamwork", "Trabajo en equipo")]
    spec = PositionSpec(requirements=base_reqs, weights={"technical": .4, "power": .25, "experience": .2, "credentials": .15})
    r = evaluate(Candidate(tech={"python": {"name": "Python"}}), spec)
    eff = sum(c["effective_weight"] for c in r["components"].values())
    checks.append({"check": "Componentes no aplicables se redistribuyen (pesos efectivos suman 1)",
                   "ok": abs(eff - 1) < 1e-3 and not r["components"]["experience"]["applicable"], "value": round(eff, 4)})

    c1 = Candidate(tech={"python": {"name": "Python"}})
    c2 = Candidate(tech={"python": {"name": "Python"}, "sql": {"name": "SQL"}})
    s1, s2 = evaluate(c1, spec)["score"], evaluate(c2, spec)["score"]
    checks.append({"check": "Monotonía: agregar una competencia exigida no baja el puntaje", "ok": s2 >= s1,
                   "value": [s1, s2]})

    from app.modules.catalog.skills import canonical_soft
    k_es, k_en = canonical_soft("Trabajo en equipo"), canonical_soft("Teamwork")
    a = evaluate(Candidate(tech={"python": {"name": "Python"}}, power={k_es: {"name": "Trabajo en equipo"}}), spec)["score"]
    b = evaluate(Candidate(tech={"python": {"name": "Python"}}, power={k_en: {"name": "Teamwork"}}), spec)["score"]
    checks.append({"check": "Equivalencia ES↔EN (Trabajo en equipo = Teamwork)", "ok": a == b and k_es == k_en, "value": [a, b]})

    r = evaluate(Candidate(tech={"sql": {"name": "SQL"}}), spec)
    checks.append({"check": "Obligatorio no cubierto quita la elegibilidad", "ok": not r["eligible"],
                   "value": r["mandatory_unmet"]})

    names = {f.name for f in fields(Candidate)}
    forbidden = {"name", "full_name", "gender", "age", "birthdate", "department", "photo", "marital_status", "origin"}
    checks.append({"check": "El contrato del motor no incluye atributos personales", "ok": not (names & forbidden),
                   "value": sorted(names)})
    return checks


def main() -> dict:
    t0 = time.time()
    cands = {e["slug"]: candidate_from_cv(e) for e in D.EMPLOYEES if e["publish"]}
    positions = {ps["title"]: ps for p in D.PROJECTS for ps in p["positions"]}
    rows, top1, top3, rr = [], 0, 0, []
    taus = []
    for title, ps in positions.items():
        rk = ranking(cands, spec_from_demo(ps))
        order = [s for s, _ in rk]
        exp = EXPECTED[title]
        pos = order.index(exp) + 1
        top1 += pos == 1
        top3 += pos <= 3
        rr.append(1 / pos)
        w = normalize_weights(ps.get("weights") or {"technical": .4, "power": .25, "experience": .2, "credentials": .15})
        for comp in ("technical", "power"):
            for delta in (-0.10, 0.10):
                w2 = dict(w)
                w2[comp] = max(0.0, w2[comp] + delta)
                taus.append(kendall_tau(order, [s for s, _ in ranking(cands, spec_from_demo(ps, w2))]))
        rows.append({"cargo": title, "esperado": exp, "posicion_esperado": pos,
                     "top3": [{"perfil": s, "puntaje": r["score"], "elegible": r["eligible"]} for s, r in rk[:3]],
                     "elegibles": sum(1 for _, r in rk if r["eligible"])})
    n = len(positions)
    report = {
        "generado": time.strftime("%Y-%m-%d %H:%M"), "segundos": round(time.time() - t0, 1),
        "perfiles": len(cands), "cargos": n,
        "acierto_top1": round(top1 / n * 100, 1), "acierto_top3": round(top3 / n * 100, 1),
        "mrr": round(sum(rr) / n, 3),
        "estabilidad_pesos_tau_promedio": round(sum(taus) / len(taus), 3), "estabilidad_pesos_tau_min": min(taus),
        "propiedades": properties(), "detalle": rows,
        "nota": "Referencia construida con datos sintéticos alineados a cada cargo: mide coherencia interna del motor, "
                "no validez predictiva con personas reales.",
    }
    out = BASE_DIR / "docs" / "reports" / "evaluacion_matching.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = all(c["ok"] for c in report["propiedades"])
    print(f"Top-1: {report['acierto_top1']} %  Top-3: {report['acierto_top3']} %  MRR: {report['mrr']}  "
          f"tau(pesos ±10): prom {report['estabilidad_pesos_tau_promedio']} / mín {report['estabilidad_pesos_tau_min']}")
    for c in report["propiedades"]:
        print(("  OK   " if c["ok"] else "  FALLA") + " " + c["check"])
    print(f"Propiedades: {'todas cumplen' if ok else 'hay fallas'} · reporte: {out.relative_to(BASE_DIR)}")
    return report


if __name__ == "__main__":
    main()
