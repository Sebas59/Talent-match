"""Parámetros del sistema editables por el administrador (persisten en BD)."""
from sqlmodel import Session

from app.core.time import utcnow
from app.modules.admin.models import SystemSetting

DEFAULT_WEIGHTS = {"technical": 0.40, "power": 0.25, "experience": 0.20, "credentials": 0.15}

DEFAULTS: dict = {
    "external_ai_allowed": True,          # política de la organización: permite IA externa si el titular autoriza
    "preferred_provider": "auto",         # auto | anthropic | gemini
    "default_weights": DEFAULT_WEIGHTS,
    "availability_threshold": 70,         # % desde el cual un perfil se considera "disponible" para un cargo
    "min_confirmed_skills_to_publish": 3,
    "retention_days": 365,
    "session_idle_note": "Token de acceso 15 min; sesión renovable 7 días.",
}

DESCRIPTIONS = {
    "external_ai_allowed": "Permitir proveedores externos de IA (siempre requiere la autorización del empleado).",
    "preferred_provider": "Proveedor externo preferido cuando hay más de uno configurado.",
    "default_weights": "Ponderaciones por defecto del matching para cargos nuevos.",
    "availability_threshold": "Compatibilidad mínima (%) para contar a alguien como talento disponible.",
    "min_confirmed_skills_to_publish": "Competencias confirmadas mínimas para publicar un perfil.",
    "retention_days": "Días de conservación de perfiles inactivos (referencia de la política).",
}


def get_setting(session: Session, key: str):
    row = session.get(SystemSetting, key)
    return row.value.get("v") if row else DEFAULTS.get(key)


def all_settings(session: Session) -> dict:
    return {k: get_setting(session, k) for k in DEFAULTS}


def set_setting(session: Session, key: str, value, actor: str | None) -> None:
    row = session.get(SystemSetting, key) or SystemSetting(key=key)
    row.value, row.updated_at, row.updated_by = {"v": value}, utcnow(), actor
    session.add(row)
