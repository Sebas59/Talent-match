"""Sesión SQLModel por request (V5). V6: activa claves foráneas en SQLite y registra todos los módulos."""
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
if _is_sqlite:
    from pathlib import Path

    _db_file = _settings.database_url.replace("sqlite:///", "", 1)
    if _db_file and _db_file != ":memory:":
        Path(_db_file).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(_settings.database_url, connect_args=_connect_args, pool_pre_ping=True)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - configuración del motor
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")   # ON DELETE CASCADE real (supresión de datos)
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


def import_models() -> None:
    from app.modules.admin import models as _ad  # noqa: F401
    from app.modules.audit import models as _a  # noqa: F401
    from app.modules.auth import models as _u  # noqa: F401
    from app.modules.consent import models as _k  # noqa: F401
    from app.modules.development import models as _d  # noqa: F401
    from app.modules.matching import models as _m  # noqa: F401
    from app.modules.privacy import models as _p  # noqa: F401
    from app.modules.profiles import models as _pr  # noqa: F401
    from app.modules.projects import models as _pj  # noqa: F401


def create_db_and_tables() -> None:
    import_models()
    SQLModel.metadata.create_all(engine)


def drop_all() -> None:
    import_models()
    SQLModel.metadata.drop_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
