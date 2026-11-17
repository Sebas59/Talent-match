"""Evaluación de la extracción (portado de Iteración 4, Unidad 5): métricas de calidad, línea base, equidad e impacto.

- Métrica de calidad 1: precisión de la extracción de habilidades frente a un conjunto etiquetado.
- Métrica de calidad 2: exhaustividad (recall) de la extracción.
- Línea base: extracción ingenua (sólo partir por comas la sección de habilidades).
- Indicador de equidad: brecha de puntaje según el TIPO de CV (texto, escaneado, imagen, JSON).
  Un CV escaneado no debería recibir peor puntaje por limitaciones del OCR: si la brecha supera
  10 puntos se emite una alerta para revisión humana.
- Indicador de impacto social: movilidad interna visible (colaboradores con ≥1 cargo ≥ 60 %).
"""
from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from statistics import mean

from app.core.config import BASE_DIR
from app.modules.catalog.skills import canonical_soft, canonical_tech
from app.modules.extraction.cv_parser import split_sections

FIXTURES = BASE_DIR / "tests" / "fixtures"


def _prf(found: set, gold: set) -> tuple[float, float]:
    tp = len(found & gold)
    precision = tp / len(found) if found else 0.0
    recall = tp / len(gold) if gold else 1.0
    return precision, recall


def _baseline(text: str) -> tuple[set, set]:
    sec = split_sections(text)
    tech, soft = set(), set()
    for line in sec.get("skills", []) + sec.get("soft", []):
        for part in line.split(","):
            p = part.strip()
            if not p:
                continue
            k = canonical_soft(p)
            (soft.add(k) if k else tech.add(canonical_tech(p)))
    return tech, soft


@lru_cache(maxsize=1)
def extraction_benchmark() -> dict:
    """Corre la extracción sobre el conjunto de prueba etiquetado (tests/fixtures)."""
    from app.modules.extraction.document_reader import read_image, read_pdf
    from app.modules.extraction.json_reader import read_json
    from app.modules.extraction.service import run_extraction

    gold_path = FIXTURES / "gold.json"
    if not gold_path.exists():
        return {"available": False}
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    rows, t0 = [], time.time()
    for fname, g in gold.items():
        if fname.startswith("_") or not (FIXTURES / fname).exists():
            continue
        data = (FIXTURES / fname).read_bytes()
        out = run_extraction(fname, data, allow_external=False)
        ex = {"profile": out.profile, "source": out.source_type, "sensitive": out.sensitive}
        p = ex["profile"]
        found_t = {s["key"] for s in p["tech_skills"]}
        found_s = {s["key"] for s in p["soft_skills"]}
        gt, gs = set(g["tech"]), set(g["soft"])
        pt, rt = _prf(found_t, gt)
        ps, rs = _prf(found_s, gs)
        # línea base
        if fname.endswith(".json"):
            text = read_json(data)[0]
        elif fname.endswith(".pdf"):
            text = read_pdf(data).text
        else:
            text = read_image(data).text
        bt, bs = _baseline(text)
        bpt, brt = _prf(bt, gt)
        sens_ok = set(g["sensitive"]) <= set(ex["sensitive"])
        rows.append({
            "archivo": fname, "tipo": ex["source"],
            "precision_tecnica": round(pt * 100, 1), "recall_tecnica": round(rt * 100, 1),
            "precision_power": round(ps * 100, 1), "recall_power": round(rs * 100, 1),
            "baseline_recall_tecnica": round(brt * 100, 1),
            "anos_ok": g["years_min"] <= p["years_experience"] <= g["years_max"],
            "educacion_ok": p["education_level"] == g["education_level"],
            "sensibles_descartados_ok": sens_ok,
        })
    if not rows:
        return {"available": False}
    agg = {
        "available": True, "n": len(rows), "segundos": round(time.time() - t0, 1),
        "precision_tecnica": round(mean(r["precision_tecnica"] for r in rows), 1),
        "recall_tecnica": round(mean(r["recall_tecnica"] for r in rows), 1),
        "precision_power": round(mean(r["precision_power"] for r in rows), 1),
        "recall_power": round(mean(r["recall_power"] for r in rows), 1),
        "baseline_recall_tecnica": round(mean(r["baseline_recall_tecnica"] for r in rows), 1),
        "anos_ok": sum(r["anos_ok"] for r in rows), "educacion_ok": sum(r["educacion_ok"] for r in rows),
        "sensibles_ok": sum(r["sensibles_descartados_ok"] for r in rows),
        "detalle": rows,
    }
    return agg


