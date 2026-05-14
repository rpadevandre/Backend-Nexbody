"""Settings: mismo `.env` que `masaas` en la raiz del repo."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Valores que nunca deben usarse en produccion
_INSECURE_DEFAULTS = {
    "changeme", "secret", "password", "formaruta", "admin",
    "test", "dev", "development", "123456", "qwerty",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongo_uri:          str = "mongodb://masaas:masaas_dev@localhost:27017/masaas?authSource=admin"
    mongo_db:           str = "masaas"
    ollama_host:        str = "http://localhost:11434"
    anthropic_api_key:  str = ""
    tavily_api_key:     str = ""
    resend_api_key:     str = ""
    resend_from:        str = "NexBody <hola@nexbody.app>"
    stripe_secret_key:       str = ""
    stripe_publishable_key:  str = ""
    stripe_webhook_secret:   str = ""
    stripe_price_monthly:    str = ""   # price_xxxxx de Stripe
    stripe_price_annual:     str = ""   # price_xxxxx de Stripe
    app_url:                 str = "http://localhost:3000"

    # Secretos criticos — requeridos en produccion
    jwt_secret_key:     str = ""
    allowed_origins:    str = ""   # CSV: "https://nexbody.app,https://panel.nexbody.app"

    # Dev mode — NUNCA activar en produccion
    dev_mode: bool = False   # DEV_MODE=true en .env habilita /auth/dev-login

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        env = os.getenv("ENV", "development")
        if env == "production":
            if not v:
                raise ValueError("JWT_SECRET_KEY es obligatorio en produccion")
            if len(v) < 32:
                raise ValueError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
            if v.lower() in _INSECURE_DEFAULTS:
                raise ValueError("JWT_SECRET_KEY usa un valor predeterminado inseguro")
        return v

    @field_validator("mongo_uri")
    @classmethod
    def validate_mongo_uri(cls, v: str) -> str:
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGO_URI debe comenzar con mongodb:// o mongodb+srv://")
        return v

    @property
    def is_production(self) -> bool:
        return os.getenv("ENV", "development") == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.allowed_origins:
            return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        return [
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3001", "http://127.0.0.1:3001",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
