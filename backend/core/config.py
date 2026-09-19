"""
The one place configuration is read.

Every setting comes from an environment variable (a local `.env` file is loaded for development). Nothing
else in the codebase calls os.getenv. In production (`ENVIRONMENT=production`) the process refuses to
start with development defaults or weak secrets, so a misconfigured deployment fails loudly at boot
instead of running insecurely.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(override=False)

DEV_APP_DB_URL = "postgresql+psycopg2://predictax_app:predictax_app_dev@localhost:5432/predictax"
DEV_ADMIN_DB_URL = "postgresql+psycopg2://predictax_owner:predictax_owner_dev@localhost:5432/predictax"
DEV_JWT_SECRET = "predictax-dev-jwt-secret-change-me-0123456789abcdef"  # noqa: S105 - marker used to reject it in production
_DEV_PASSWORD_MARKERS = ("_dev@", "_dev:", "changeme", "change-me")
_TRUE = {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str) -> bool:
    return _env(name).lower() in _TRUE


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str

    database_url: str
    admin_database_url: str
    app_db_role: str
    db_pool_size: int
    db_max_overflow: int

    auth_base_url: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    redis_url: str
    upload_dir: Path
    model_dir: Path
    max_upload_mb: int

    xai_api_key: str
    grok_model: str
    allow_paid_sentiment: bool

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def model_signing_key(self) -> bytes:
        """Key that signs saved ML artifacts (derived from the auth secret so there is nothing extra to manage)."""
        return f"predictax-model-artifacts:{self.supabase_jwt_secret}".encode()

    def problems(self) -> list[str]:
        """Everything wrong with this configuration for a production deployment."""
        issues: list[str] = []
        for name, url in (("DATABASE_URL", self.database_url), ("ADMIN_DATABASE_URL", self.admin_database_url)):
            if any(marker in url for marker in _DEV_PASSWORD_MARKERS):
                issues.append(f"{name} uses a development password.")
        if self.database_url == self.admin_database_url:
            issues.append("DATABASE_URL and ADMIN_DATABASE_URL must be different roles: the app role must not own the tables.")
        secret = self.supabase_jwt_secret
        if not secret or secret == DEV_JWT_SECRET or "change-me" in secret or len(secret) < 32:
            issues.append("SUPABASE_JWT_SECRET is missing, a development default, or shorter than 32 characters.")
        if not (self.auth_base_url or self.supabase_url):
            issues.append("Set AUTH_BASE_URL or SUPABASE_URL.")
        for name, url in (("AUTH_BASE_URL", self.auth_base_url), ("SUPABASE_URL", self.supabase_url)):
            parsed = urlparse(url)
            if url and parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "auth", "db"):
                issues.append(f"{name} must use https (plain http is only acceptable inside a private network).")
        if self.redis_url:
            parsed = urlparse(self.redis_url)
            if not parsed.password and parsed.hostname not in ("localhost", "127.0.0.1"):
                issues.append("REDIS_URL has no password.")
        return issues

    def assert_production_ready(self) -> None:
        if self.is_production and (issues := self.problems()):
            raise RuntimeError("Refusing to start with an insecure production configuration:\n  - "
                               + "\n  - ".join(issues))


def get_settings() -> Settings:
    """Build settings from the current environment (cheap; read fresh so tests can change the environment)."""
    return Settings(
        environment=_env("ENVIRONMENT", "development").lower(),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        database_url=_env("DATABASE_URL") or DEV_APP_DB_URL,
        admin_database_url=_env("ADMIN_DATABASE_URL") or DEV_ADMIN_DB_URL,
        app_db_role=_env("APP_DB_ROLE", "predictax_app"),
        db_pool_size=int(_env("DB_POOL_SIZE", "10")),
        db_max_overflow=int(_env("DB_MAX_OVERFLOW", "20")),
        auth_base_url=_env("AUTH_BASE_URL").rstrip("/"),
        supabase_url=_env("SUPABASE_URL").rstrip("/"),
        supabase_anon_key=_env("SUPABASE_ANON_KEY"),
        supabase_service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_jwt_secret=_env("SUPABASE_JWT_SECRET"),
        redis_url=_env("REDIS_URL"),
        upload_dir=Path(_env("UPLOAD_DIR", "./data/uploads")).resolve(),
        model_dir=Path(_env("MODEL_DIR", "models")).resolve(),
        max_upload_mb=int(_env("MAX_UPLOAD_MB", "500")),
        xai_api_key=_env("XAI_API_KEY"),
        grok_model=_env("GROK_MODEL", "grok-3-mini"),
        allow_paid_sentiment=_flag("ALLOW_PAID_SENTIMENT"),
    )
