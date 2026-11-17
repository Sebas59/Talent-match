import pytest


def test_seed_refuses_in_production(monkeypatch):
    from app.core.config import get_settings
    from scripts import seed_demo
    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(SystemExit):
        seed_demo.seed(reset=True, quiet=True)


def test_seed_refuses_reset_with_real_users(client, monkeypatch):
    """Si existe un usuario NO demo (p. ej. la invitada Ana Prueba), --reset no borra nada."""
    from sqlmodel import Session, func, select

    from app.core.database import engine
    from app.modules.auth.models import User
    from scripts import seed_demo
    with Session(engine) as s:
        before = s.exec(select(func.count()).select_from(User)).one()
        real = s.exec(select(func.count()).select_from(User).where(User.is_demo == False)).one()  # noqa: E712
    if real == 0:
        pytest.skip("No hay usuarios no demo en esta ejecución")
    with pytest.raises(SystemExit):
        seed_demo.seed(reset=True, quiet=True)
    with Session(engine) as s:
        assert s.exec(select(func.count()).select_from(User)).one() == before
