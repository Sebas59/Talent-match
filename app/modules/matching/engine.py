"""Motor de matching explicable (V6). Base: motor de Iteración 4 (crédito parcial, sinónimos ES↔EN,
habilidades relacionadas). V6 agrega requisitos obligatorios/deseables, certificaciones, componentes
no aplicables con redistribución explícita de pesos y explicación completa del cálculo.

Puntaje = 100 · Σ_i  ŵ_i · c_i      con ŵ normalizado sobre los componentes APLICABLES
  c_tecnico, c_power  = Σ(crédito_r · peso_r) / Σ peso_r      peso_r = peso · 1,5 si es obligatorio
  c_experiencia       = min(1, años / años mínimos)
  c_credenciales      = promedio(educación, cobertura de certificaciones exigidas)
Crédito por requisito: 1,0 exacta (con sinónimos) · 0,85 casi idéntica · 0,7 contenida · 0,6 relacionada.

Solo se usan variables laborales. Nunca se usan nombre, edad, género, foto, estado civil, origen, salud,
departamento ni cualquier otro atributo personal o proxy de ellos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.core.text import norm
from app.modules.catalog.skills import EDU_LEVELS

ENGINE_VERSION = "v6-explainable-1"
MANDATORY_FACTOR = 1.5
MET, PARTIAL = 0.85, 0.6
MANDATORY_MIN = 0.7  # un obligatorio cubierto solo por una habilidad "relacionada" (0,6) no habilita la elegibilidad
COMPONENTS = ("technical", "power", "experience", "credentials")
COMPONENT_LABELS = {"technical": "Competencias técnicas", "power": "Power skills", "experience": "Experiencia",
                    "credentials": "Certificaciones y formación"}

RELATED = {
    "sql": {"mysql", "postgresql", "sql server", "oracle", "databases"},
    "databases": {"mysql", "postgresql", "sql server", "oracle", "mongodb", "sql", "nosql", "database management"},
    "nosql": {"mongodb", "cassandra", "redis", "elasticsearch"},
    "cloud computing": {"aws", "microsoft azure", "google cloud platform"},
    "aws": {"cloud computing", "microsoft azure", "google cloud platform"},
    "microsoft azure": {"aws", "google cloud platform", "cloud computing"},
    "google cloud platform": {"aws", "microsoft azure", "cloud computing"},
    "machine learning": {"deep learning", "scikit-learn", "tensorflow", "pytorch", "data science", "artificial intelligence"},
    "deep learning": {"tensorflow", "pytorch", "keras", "neural networks", "machine learning"},
    "artificial intelligence": {"machine learning", "deep learning", "natural language processing"},
    "data science": {"machine learning", "data analysis", "statistics", "python", "r"},
    "data analysis": {"data science", "statistics", "excel", "data visualization", "sql"},
    "data visualization": {"tableau", "power bi", "data analysis"},
    "business intelligence": {"power bi", "tableau", "data warehousing", "data visualization"},
    "big data": {"apache spark", "hadoop", "apache kafka", "hive"},
    "apache spark": {"big data", "hadoop", "scala"},
    "hadoop": {"big data", "apache spark", "hive"},
    "full stack development": {"front-end development", "back-end development", "web development", "javascript"},
    "back-end development": {"node.js", "java", "python", "spring boot", "django", "fastapi", "rest api"},
    "front-end development": {"react", "angular", "vue.js", "javascript", "html", "css"},
    "web development": {"html", "css", "javascript", "react", "angular"},
    "javascript": {"typescript", "react", "angular", "node.js", "vue.js"},
    "react": {"javascript", "react native"},
    "angular": {"typescript", "javascript"},
    "software development": {"java", "python", "c#", "javascript", "object-oriented programming"},
    "statistics": {"statistical analysis", "r", "data analysis"},
    "statistical analysis": {"statistics", "r", "sas"},
    "etl": {"data pipelines", "data warehousing", "apache airflow", "data engineering"},
    "data pipelines": {"etl", "apache airflow", "apache kafka", "data engineering"},
    "data engineering": {"etl", "data pipelines", "apache spark", "sql"},
    "information security": {"firewalls", "networking", "security compliance"},
    "networking": {"tcp/ip", "firewalls", "cisco"},
    "system administration": {"linux", "windows server", "active directory"},
    "devops": {"ci/cd", "docker", "kubernetes", "jenkins"},
    "ci/cd": {"devops", "jenkins", "git"},
    "agile": {"scrum"},
    "scrum": {"agile"},
    "project management": {"agile", "scrum"},
}


@dataclass
class Candidate:
    tech: dict[str, dict] = field(default_factory=dict)    # key -> {name, evidence, origin}
    power: dict[str, dict] = field(default_factory=dict)
    certifications: list[str] = field(default_factory=list)
    years: float = 0.0
    edu_level: int = 0


@dataclass
class Requirement:
    kind: str
    key: str
    name: str
    importance: str = "desirable"
    weight: float = 1.0


@dataclass
class PositionSpec:
    requirements: list[Requirement]
    weights: dict
    min_years: float = 0.0
    min_years_mandatory: bool = False
    education_level: int = 0


def normalize_weights(w: dict | None) -> dict:
    vals = {k: max(0.0, float((w or {}).get(k, 0) or 0)) for k in COMPONENTS}
    total = sum(vals.values())
    if total <= 0:
        return {k: 0.25 for k in COMPONENTS}
    return {k: round(v / total, 4) for k, v in vals.items()}


def _phrase_in(small: str, big: str) -> bool:
    if len(small) < 3 and small not in {"r", "c", "go"}:
        return False
    return re.search(r"(^|[\s/(,-])" + re.escape(small) + r"($|[\s/),-])", big) is not None


def skill_credit(req_key: str, cv: dict[str, dict]) -> tuple[float, str | None, str]:
    """Crédito [0,1], clave de la habilidad del CV que lo respalda y tipo de coincidencia."""
    if req_key in cv:
        return 1.0, req_key, "exacta"
    best, who, how = 0.0, None, ""
    for k in cv:
        c, h = 0.0, ""
        if len(k) >= 3 and len(req_key) >= 3:
            if fuzz.token_set_ratio(k, req_key) >= 92:
                c, h = 0.85, "casi idéntica"
            elif _phrase_in(k, req_key) or _phrase_in(req_key, k):
                c, h = 0.7, "contenida"
        if c < 0.6 and (k in RELATED.get(req_key, ()) or req_key in RELATED.get(k, ())):
            c, h = 0.6, "relacionada"
        if c > best:
            best, who, how = c, k, h
    return best, who, how


def cert_credit(req: Requirement, certs: list[str]) -> tuple[float, str | None, str]:
    target = norm(req.name)
    best, who, how = 0.0, None, ""
    for c in certs:
        n = norm(c)
        if not n:
            continue
        ratio = fuzz.token_set_ratio(target, n)
        if ratio >= 90 or (len(target) >= 4 and _phrase_in(target, n)):
            return 1.0, c, "exacta"
        if ratio >= 72 and best < 0.6:
            best, who, how = 0.6, c, "relacionada"
    return best, who, how


def experience_credit(years: float, min_years: float) -> float:
    return 1.0 if min_years <= 0 else max(0.0, min(1.0, years / min_years))


def education_credit(cv_level: int, req_level: int) -> float:
    if req_level <= 0:
        return 1.0
    if cv_level <= 0:
        return 0.4
    if cv_level >= req_level:
        return 1.0
    return 0.7 if cv_level == req_level - 1 else 0.35


def _status(credit: float) -> str:
    return "met" if credit >= MET else ("partial" if credit >= PARTIAL else "missing")


def evaluate(cand: Candidate, pos: PositionSpec) -> dict:
    groups = {"tech": [], "power": [], "certification": []}
    for r in pos.requirements:
        groups.setdefault(r.kind, []).append(r)

    req_rows: list[dict] = []
    sums = {}
    for kind, store in (("tech", cand.tech), ("power", cand.power)):
        got = tot = 0.0
        for r in groups[kind]:
            credit, by, how = skill_credit(r.key, store)
            w = r.weight * (MANDATORY_FACTOR if r.importance == "mandatory" else 1.0)
            got, tot = got + credit * w, tot + w
            ev = store.get(by) if by else None
            req_rows.append({"kind": kind, "key": r.key, "name": r.name, "importance": r.importance,
                             "weight": round(w, 2), "credit": round(credit, 2), "status": _status(credit),
                             "match_type": how, "matched_with": ev["name"] if ev else None,
                             "evidence": ev.get("evidence") if ev else None, "origin": ev.get("origin") if ev else None})
        sums[kind] = (got / tot) if tot else None
    cert_got = cert_tot = 0.0
    for r in groups["certification"]:
        credit, by, how = cert_credit(r, cand.certifications)
        w = r.weight * (MANDATORY_FACTOR if r.importance == "mandatory" else 1.0)
        cert_got, cert_tot = cert_got + credit * w, cert_tot + w
        req_rows.append({"kind": "certification", "key": r.key, "name": r.name, "importance": r.importance,
                         "weight": round(w, 2), "credit": round(credit, 2), "status": _status(credit),
                         "match_type": how, "matched_with": by, "evidence": by, "origin": None})

    comp_value: dict[str, float | None] = {
        "technical": sums["tech"],
        "power": sums["power"],
        "experience": experience_credit(cand.years, pos.min_years) if pos.min_years > 0 else None,
    }
    cred_parts = []
    if pos.education_level > 0:
        cred_parts.append(education_credit(cand.edu_level, pos.education_level))
    if cert_tot:
        cred_parts.append(cert_got / cert_tot)
    comp_value["credentials"] = (sum(cred_parts) / len(cred_parts)) if cred_parts else None

    base_w = normalize_weights(pos.weights)
    applicable = [k for k in COMPONENTS if comp_value[k] is not None]
    w_sum = sum(base_w[k] for k in applicable) or 1.0
    eff_w = {k: (base_w[k] / w_sum if k in applicable else 0.0) for k in COMPONENTS}
    total = sum(eff_w[k] * (comp_value[k] or 0.0) for k in applicable)

    components = {k: {"label": COMPONENT_LABELS[k], "applicable": k in applicable,
                      "configured_weight": base_w[k], "effective_weight": round(eff_w[k], 4),
                      "value": round((comp_value[k] or 0) * 100, 1) if k in applicable else None,
                      "points": round(eff_w[k] * (comp_value[k] or 0) * 100, 1)} for k in COMPONENTS}

    unmet = [r for r in req_rows if r["importance"] == "mandatory" and r["credit"] < MANDATORY_MIN]
    partial_mand = [r for r in req_rows if r["importance"] == "mandatory" and MANDATORY_MIN <= r["credit"] < MET]
    for r in req_rows:
        r["blocks_eligibility"] = r["importance"] == "mandatory" and r["credit"] < MANDATORY_MIN
    exp_unmet = pos.min_years_mandatory and pos.min_years > 0 and cand.years < pos.min_years
    unmet_names = [r["name"] for r in unmet] + ([f"Experiencia mínima de {pos.min_years:g} años"] if exp_unmet else [])

    matched = [r for r in req_rows if r["status"] == "met"]
    partial = [r for r in req_rows if r["status"] == "partial"]
    missing = [r for r in req_rows if r["status"] == "missing"]
    key = lambda r: (r["importance"] != "mandatory", -r["weight"])  # noqa: E731
    strengths = [f"Cumple «{r['name']}»" + (" (obligatorio)" if r["importance"] == "mandatory" else "")
                 for r in sorted(matched, key=key)[:5]]
    if pos.min_years > 0 and cand.years >= pos.min_years:
        strengths.append(f"Experiencia acreditada de {cand.years:g} años (se piden {pos.min_years:g}).")
    if pos.education_level and cand.edu_level >= pos.education_level:
        strengths.append(f"Formación: {EDU_LEVELS.get(cand.edu_level)} (se pide {EDU_LEVELS.get(pos.education_level)}).")

    explanation = []
    for k in COMPONENTS:
        c = components[k]
        if c["applicable"]:
            explanation.append(f"{c['label']}: {c['value']:g} % × peso {c['effective_weight'] * 100:.0f} % = "
                               f"{c['points']:g} puntos.")
    na = [COMPONENT_LABELS[k] for k in COMPONENTS if k not in applicable]
    if na:
        explanation.append("No aplican (el cargo no los exige): " + ", ".join(na)
                           + ". Su peso se repartió proporcionalmente entre los demás componentes.")
    n_t = len(groups["tech"])
    if n_t:
        explanation.append(f"Técnicas: cumple {sum(1 for r in matched if r['kind'] == 'tech')} de {n_t}, "
                           f"{sum(1 for r in partial if r['kind'] == 'tech')} de forma parcial.")
    if pos.min_years > 0:
        gap = pos.min_years - cand.years
        explanation.append(f"Experiencia: acredita {cand.years:g} de {pos.min_years:g} años"
                           + (f" (faltan {gap:.1f})." if gap > 0 else "."))
    if unmet_names:
        explanation.append("Requisitos obligatorios no cumplidos (o cubiertos solo por una habilidad relacionada): "
                           + ", ".join(unmet_names) + ".")
    if partial_mand:
        explanation.append("Obligatorios cubiertos solo parcialmente: " + ", ".join(r["name"] for r in partial_mand) + ".")
    explanation.append("El puntaje resume la información confirmada del perfil frente a los requisitos; "
                       "no mide el potencial ni el desempeño de la persona.")

    return {
        "score": round(total * 100, 1),
        "eligible": not unmet_names,
        "components": components,
        "requirements": req_rows,
        "matched": [r["name"] for r in sorted(matched, key=key)],
        "partial": [r["name"] for r in sorted(partial, key=key)],
        "missing": [r["name"] for r in sorted(missing, key=key)],
        "mandatory_unmet": unmet_names,
        "strengths": strengths,
        "gaps": [{"name": r["name"], "kind": r["kind"], "key": r["key"], "importance": r["importance"],
                  "credit": r["credit"], "weight": r["weight"]} for r in sorted(missing + partial, key=key)],
        "evidence": [{"requirement": r["name"], "matched_with": r["matched_with"], "evidence": r["evidence"],
                      "origin": r["origin"], "match_type": r["match_type"]} for r in matched + partial if r["evidence"]],
        "explanation": explanation,
        "engine": ENGINE_VERSION,
    }
