"""
Application configuration — all environment variables are declared here.
In development: values come from the .env file.
In production / Docker: set the vars directly in the environment (never commit secrets).

Required env vars:
  GROQ_API_KEY  — Groq LLM API key (set in env, not committed to git)

Optional env vars:
  DATA_LAKE_DIR — absolute path to the datasets folder (default: auto-detected)
  BACKEND_URL   — base URL for the FastAPI backend
  BACKEND_PORT  — FastAPI port (default: 8000)
  STREAMLIT_PORT — Streamlit port (default: 8501)
  DATABASE_URL  — SQLAlchemy database URL
  ENVIRONMENT   — development | staging | production
  DEBUG         — enable debug logging (default: true in dev)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Default data lake location — overridden by DATA_LAKE_DIR env var (D6)
_DEFAULT_DATA_LAKE = str(BASE_DIR / "datasets" / "UAE_REAL_ESTATE_DATA_LAKE" / "datasets")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Secrets (D4) — set via env var; NEVER commit values to git ────
    GROQ_API_KEY: str = ""
    NEWS_API_KEY: str = ""

    # ── Service configuration ──────────────────────────────────────────
    DATABASE_URL:   str  = f"sqlite:///{BASE_DIR}/uae_platform.db"
    BACKEND_URL:    str  = "http://localhost:8000"
    BACKEND_PORT:   int  = 8000
    STREAMLIT_PORT: int  = 8501
    ENVIRONMENT:    str  = "development"   # development | staging | production
    DEBUG:          bool = True

    # ── Data paths — override DATA_LAKE_DIR for Docker/cloud (D6) ─────
    DATA_LAKE_DIR: str = _DEFAULT_DATA_LAKE

    # ── Path accessors (derived from DATA_LAKE_DIR) ────────────────────

    @property
    def data_lake(self) -> Path:
        return Path(self.DATA_LAKE_DIR)

    @property
    def real_estate_dir(self) -> Path:
        return self.data_lake / "real_estate"

    @property
    def macro_dir(self) -> Path:
        return self.data_lake / "macroeconomic"

    @property
    def infra_dir(self) -> Path:
        return self.data_lake / "infrastructure"

    @property
    def competitive_dir(self) -> Path:
        return self.data_lake / "competitive"

    @property
    def news_dir(self) -> Path:
        return self.data_lake / "news"

    @property
    def models_dir(self) -> Path:
        p = BASE_DIR / "models"
        p.mkdir(exist_ok=True)
        return p

    def validate_paths(self) -> None:
        """Log clear warnings at startup if critical dataset directories are missing (D7)."""
        critical = {
            "Real estate data":  self.real_estate_dir,
            "Macroeconomic data": self.macro_dir,
            "Infrastructure data": self.infra_dir,
        }
        for label, path in critical.items():
            if not path.exists():
                log.warning(
                    "%s directory not found: %s — dependent endpoints will return empty results.",
                    label, path,
                )
            else:
                log.info("%s: %s  ✓", label, path)
        if not self.GROQ_API_KEY:
            log.warning(
                "GROQ_API_KEY is not set — AI-powered features will use fallback responses. "
                "Set it in .env (development) or as an environment variable (production)."
            )


settings = Settings()
