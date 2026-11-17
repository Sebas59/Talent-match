"""Repositorio de datasets (plantillas de cargos y catálogo de cursos). Origen: Iteración 4 + validación de V5.

Lee JobsDatasetProcessed.csv, Coursera.csv y Udemy_Courses.xlsx una sola vez y los
deja en memoria. La lógica de negocio nunca abre archivos directamente.
"""
from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from urllib.parse import urlparse

from app.core.config import get_settings

# V5: los enlaces de cursos se limitan a dominios conocidos (evita enlaces maliciosos en el catálogo)
ALLOWED_COURSE_HOSTS = {"www.coursera.org", "coursera.org", "www.udemy.com", "udemy.com"}


def _path(name: str):
    return get_settings().data_dir / name


def _clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    return df


@lru_cache(maxsize=1)
def load_jobs() -> pd.DataFrame:
    df = _clean_cols(pd.read_csv(_path(get_settings().jobs_file), encoding="utf-8"))
    for col in ["Query", "Job Title", "Description", "IT Skills", "Soft Skills", "Education", "Experience"]:
        df[col] = df[col].fillna("").astype(str)
    df["Job Title"] = df["Job Title"].str.strip()
    df = df.drop_duplicates(subset=["ID"]).set_index("ID", drop=False)
    return df


def _to_float(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _hours(value) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    return float(m.group(1)) if m else None


@lru_cache(maxsize=1)
def load_courses() -> pd.DataFrame:
    """Unifica ambos catálogos en un único esquema."""
    cz = _clean_cols(pd.read_csv(_path(get_settings().coursera_file), encoding="utf-8", encoding_errors="replace"))
    coursera = pd.DataFrame({
        "platform": "Coursera",
        "title": cz["Course Name"].astype(str).str.strip(),
        "provider": cz["University"].fillna("Coursera").astype(str).str.strip(),
        "level": cz["Difficulty Level"].fillna("No especificado").astype(str).str.strip(),
        "rating": cz["Course Rating"].map(_to_float),
        "url": cz["Course URL"].astype(str).str.strip(),
        "skills": cz["Skills"].fillna("").astype(str),
        "description": cz["Course Description"].fillna("").astype(str).str.slice(0, 600),
        "hours": None,
    })
    ud = _clean_cols(pd.read_excel(_path(get_settings().udemy_file)))
    udemy = pd.DataFrame({
        "platform": "Udemy",
        "title": ud["Course Title"].astype(str).str.strip(),
        "provider": ud["Course Instructor Name"].fillna("Udemy").astype(str).str.strip(),
        "level": ud["Course Levels"].fillna("All Levels").astype(str).str.strip(),
        "rating": ud["Ratings"].map(_to_float),
        "url": ud["Course Links"].astype(str).str.strip(),
        "skills": ud["Skills You Gain"].fillna("").astype(str),
        "description": "",
        "hours": ud["Total Course Hours"].map(_hours),
    })
    df = pd.concat([coursera, udemy], ignore_index=True)
    df = df[df["url"].map(lambda u: urlparse(u).scheme == "https" and urlparse(u).hostname in ALLOWED_COURSE_HOSTS)]
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    return df


@lru_cache(maxsize=1)
def dataset_stats() -> dict:
    jobs = load_jobs()
    courses = load_courses()
    rated = courses[courses["rating"].notna()]
    return {
        "jobs": int(len(jobs)),
        "job_categories": int(jobs["Query"].nunique()),
        "courses": int(len(courses)),
        "coursera": int((courses["platform"] == "Coursera").sum()),
        "udemy": int((courses["platform"] == "Udemy").sum()),
        "courses_over_4": int((rated["rating"] > 4.0).sum()),
    }


def release_memory() -> None:
    """Libera los DataFrames crudos (ya procesados) y devuelve la memoria al sistema operativo.

    Importante en planes con poca RAM (p. ej. Render gratuito, 512 MB).
    """
    load_jobs.cache_clear()
    load_courses.cache_clear()
    trim_memory()


def trim_memory() -> None:
    import ctypes
    import gc

    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):  # Windows / macOS: no aplica
        pass
