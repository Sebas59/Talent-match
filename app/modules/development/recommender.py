"""Recomendador de cursos (Iteración 4) sobre Coursera.csv y Udemy_Courses.xlsx.

Los cursos provienen de los datasets del proyecto (registros públicos de referencia). La disponibilidad,
el precio y la vigencia de cada curso no se verifican en línea: la interfaz lo indica.

Sólo se recomiendan cursos con calificación ESTRICTAMENTE mayor a 4.0.
La relevancia se calcula con TF-IDF (título + habilidades del curso) y se combina con
la calificación. Cada brecha recibe hasta un curso por plataforma.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.text import fix_mojibake, norm
from app.modules.catalog.datasets import load_courses
from app.modules.catalog.skills import SOFT_CANON, soft_query

MIN_COURSE_RATING = 4.0  # estrictamente mayor

LEVEL_HOURS = {"beginner": 14, "intermediate": 22, "advanced": 30, "mixed": 18, "conversant": 16}
LEVEL_ES = {"beginner": "Principiante", "intermediate": "Intermedio", "advanced": "Avanzado", "mixed": "Mixto",
            "all levels": "Todos los niveles", "expert": "Experto", "conversant": "Intermedio"}
HOURS_PER_WEEK = 6


@lru_cache(maxsize=1)
def _index():
    df = load_courses()
    df = df[df["rating"].notna() & (df["rating"] > MIN_COURSE_RATING)].reset_index(drop=True)
    title = df["title"].map(norm)
    skills = df["skills"].map(lambda s: norm(fix_mojibake(s)))
    desc = df["description"].map(lambda s: norm(fix_mojibake(s))[:300])
    corpus = (title + " ") * 3 + (skills + " ") * 2 + desc
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words="english")
    mat = vec.fit_transform(corpus)
    df = df.drop(columns=["description"])   # ya no se necesita: ahorra memoria
    return df, vec, mat, title.tolist()


QUERY_EXPANSION = {
    "r": "r programming", "c": "c programming language", "go": "go golang programming", "aws": "aws amazon web services",
    "sql": "sql databases queries", "git": "git github version control", "ci/cd": "ci cd continuous integration devops",
    ".net": "net c# asp", "c#": "c# programming", "c++": "c++ programming", "etl": "etl data pipelines",
    "rest api": "rest api", "html": "html web", "css": "css web", "nosql": "nosql mongodb",
}
WEAK_TOKENS = {"iii", "ii", "skills", "skill", "management", "data", "analysis", "development", "programming",
               "and", "the", "for", "with", "web", "language", "tools", "systems", "system"}


def _query_for(skill: dict) -> str:
    if skill.get("type") == "power":
        return soft_query(skill["key"]) if skill["key"] in SOFT_CANON else skill["name"]
    return QUERY_EXPANSION.get(skill["key"], skill["key"])


def courses_for_skill(skill: dict, exclude: set[str], per_platform: int = 1) -> list[dict]:
    df, vec, mat, titles = _index()
    if skill.get("type") == "power" and skill["key"] not in SOFT_CANON:
        return []  # power skill no canónica: se reporta la brecha sin forzar un curso poco pertinente
    q = _query_for(skill)
    qv = vec.transform([norm(q)])
    if qv.nnz == 0:
        return []
    sims = (mat @ qv.T).toarray().ravel()
    q_tokens = [t for t in re.findall(r"[a-z0-9\+#\.]+", norm(skill.get("key", q))) if len(t) > 1 or t in {"r", "c"}]
    strong = [t for t in re.findall(r"[a-z0-9\+#\.]+", norm(q)) if (len(t) >= 3 or t in {"c#", "r", "go"}) and t not in WEAK_TOKENS]
    # Bonus si el término aparece literalmente en el título
    bonus = np.array([0.15 if q_tokens and all(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", ti) for t in q_tokens) else 0.0
                      for ti in titles]) if len(q_tokens) <= 3 else 0.0
    rating_norm = (df["rating"].to_numpy() - 4.0) / 1.0
    score = sims + bonus + 0.08 * rating_norm
    order = np.argsort(-score)
    picked: list[dict] = []
    per = {"Coursera": 0, "Udemy": 0}
    for i in order[:200]:
        if sims[i] < 0.12:
            break
        row = df.iloc[i]
        def _has(text: str) -> bool:
            return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", text) for t in strong)

        if strong and not (_has(titles[i]) or (sims[i] >= 0.35 and _has(norm(row["skills"])))):
            continue
        if not strong and sims[i] < 0.3:
            continue
        if row["url"] in exclude or per[row["platform"]] >= per_platform:
            continue
        lvl_raw = str(row["level"]).strip().lower()
        hours = row["hours"]
        estimated = False
        if hours is None or (isinstance(hours, float) and np.isnan(hours)):
            hours = LEVEL_HOURS.get(lvl_raw, 18)
            estimated = True
        picked.append({
            "platform": row["platform"], "course_title": fix_mojibake(row["title"])[:300],
            "provider": fix_mojibake(row["provider"])[:200], "rating": float(row["rating"]),
            "level": LEVEL_ES.get(lvl_raw, str(row["level"]).title()), "hours": round(float(hours), 1),
            "hours_estimated": estimated, "url": row["url"], "relevance": round(float(sims[i]), 3),
        })
        per[row["platform"]] += 1
        exclude.add(row["url"])
        if all(v >= per_platform for v in per.values()):
            break
    return picked


def recommend_for_gaps(gaps: list[dict], max_items: int = 8, per_platform: int = 1) -> list[dict]:
    """gaps: [{name, key, kind(tech|power|certification), importance}]. Cada recomendación cita su brecha."""
    exclude: set[str] = set()
    out = []
    for g in gaps:
        if g.get("kind") == "certification":
            out.append({"skill": g["name"], "skill_key": g.get("key"), "kind": "certification",
                        "importance": g.get("importance"), "courses": [],
                        "note": "Certificación exigida: consulte la entidad certificadora oficial."})
            continue
        skill = {"key": g.get("key") or norm(g["name"]), "name": g["name"],
                 "type": "power" if g.get("kind") == "power" else "tecnica"}
        try:
            courses = courses_for_skill(skill, exclude, per_platform=per_platform)
        except Exception:  # catálogo no disponible: se reporta la brecha sin curso
            courses = []
        out.append({"skill": g["name"], "skill_key": skill["key"], "kind": g.get("kind", "tech"),
                    "importance": g.get("importance"), "courses": courses,
                    "note": None if courses else "Sin curso pertinente en el catálogo; se sugiere formación interna."})
        if len(out) >= max_items:
            break
    return out


def warm() -> int:
    df, *_ = _index()
    return len(df)
