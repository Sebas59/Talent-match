"""Empaqueta el proyecto en un ZIP reproducible (excluye secretos, bases de datos y dependencias).

Uso:  python -m scripts.package   ->   TalentMatch_V6.zip en la carpeta superior
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".git"}
EXCLUDE_FILES = {".env"}
EXCLUDE_SUFFIX = {".db", ".db-wal", ".db-shm", ".pyc"}


def main() -> Path:
    out = ROOT.parent / "TalentMatch_V6.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(ROOT.rglob("*")):
            rel = p.relative_to(ROOT)
            if any(part in EXCLUDE_DIRS for part in rel.parts) or p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIX:
                continue
            if p.is_file():
                z.write(p, Path("TalentMatch_V6") / rel)
    print(f"ZIP creado: {out}")
    return out


if __name__ == "__main__":
    main()
