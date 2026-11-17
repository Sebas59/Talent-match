"""Crea las tablas de forma reproducible (idempotente). Uso:  python -m scripts.init_db"""
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import create_db_and_tables, engine
from app.modules.auth.service import seed_admin

if __name__ == "__main__":
    create_db_and_tables()
    with Session(engine) as s:
        seed_admin(s)
    print(f"Base de datos lista: {get_settings().database_url.split('?')[0]}")
