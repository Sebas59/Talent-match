"""Configuración centralizada (12-factor). Todo secreto viene de variables de entorno / .env.

Base: V5 (pydantic-settings + SecretStr). V6 agrega roles, sesiones revocables, invitaciones,
proveedores de IA intercambiables y modo demo.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "Talent Match"
    app_version: str = "6.0.0"
    environment: Literal["development", "test", "production"] = "development"
    organization_name: str = "Organización Demo S.A.S."

    # --- Seguridad / JWT ---
    secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "talentmatch"
    jwt_audience: str = "talentmatch-api"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False  # True detrás de HTTPS

    # Claves Fernet: una o varias separadas por coma (la primera cifra; todas descifran -> rotación)
    field_encryption_key: SecretStr
    # Clave HMAC para índices ciegos. Si no se define se usa SECRET_KEY (compatibilidad V5).
    blind_index_key: SecretStr | None = None

    # --- Administrador inicial (solo si no existe ningún administrador) ---
    admin_email: EmailStr | None = None
    admin_password: SecretStr | None = None

    # --- Red ---
    allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # --- Persistencia y datos ---
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'talentmatch_v6.db').as_posix()}"
    data_dir: Path = BASE_DIR / "data"
    frontend_dist: Path = BASE_DIR / "frontend" / "dist"
    jobs_file: str = "JobsDatasetProcessed.csv"
    coursera_file: str = "Coursera.csv"
    udemy_file: str = "Udemy_Courses.xlsx"

    # --- Límites (Disponibilidad) ---
    max_upload_mb: int = Field(default=5, ge=1, le=20)
    max_pdf_pages: int = Field(default=10, ge=1, le=40)
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    rate_limit_per_minute: int = 120
    invitation_days: int = Field(default=7, ge=1, le=30)

    # --- IA (opcional). Sin claves funciona el proveedor local ---
    ai_provider: Literal["auto", "local", "anthropic", "gemini"] = "auto"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: int = Field(default=45, ge=5, le=120)

    # --- Privacidad ---
    consent_policy_version: str = "2026-11-v6"
    data_controller: str = "Área de Talento Humano — Organización Demo S.A.S. (proyecto académico)"
    data_contact_email: EmailStr = "privacidad@talentmatch.demo"
    retention_days: int = Field(default=365, ge=1)

    # --- Demo ---
    demo_mode: bool = True  # habilita la semilla de demostración; en producción debe ser False
    warm_catalog_on_start: bool = True

    @field_validator("anthropic_api_key", "gemini_api_key", "blind_index_key", "admin_password", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return v or None

    @field_validator("admin_email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        return v or None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
