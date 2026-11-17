"""Crea el archivo .env con secretos aleatorios a partir de .env.example (no sobrescribe uno existente).

Uso:  python -m scripts.setup_env
"""
import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    env, example = ROOT / ".env", ROOT / ".env.example"
    if env.exists() and "--force" not in sys.argv:
        print(".env ya existe; no se modificó. Use --force para regenerarlo (invalida los datos cifrados existentes).")
        return
    values = {"SECRET_KEY": secrets.token_urlsafe(64), "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
              "BLIND_INDEX_KEY": secrets.token_urlsafe(64)}
    out = []
    for line in example.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip()
        out.append(f"{key}={values[key]}" if key in values and line.strip().endswith("=") else line)
    env.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Archivo .env creado con secretos nuevos. No lo comparta ni lo suba al repositorio.")


if __name__ == "__main__":
    main()
