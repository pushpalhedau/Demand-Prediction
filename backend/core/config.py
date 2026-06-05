from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_LAKE = BASE_DIR / "datasets" / "UAE_REAL_ESTATE_DATA_LAKE" / "datasets"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/uae_platform.db"
    DEBUG: bool = True
    GROQ_API_KEY: str = ""
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_PORT: int = 8000
    STREAMLIT_PORT: int = 8501

    # Dataset paths
    @property
    def real_estate_dir(self) -> Path:
        return DATA_LAKE / "real_estate"

    @property
    def macro_dir(self) -> Path:
        return DATA_LAKE / "macroeconomic"

    @property
    def infra_dir(self) -> Path:
        return DATA_LAKE / "infrastructure"

    @property
    def competitive_dir(self) -> Path:
        return DATA_LAKE / "competitive"

    @property
    def news_dir(self) -> Path:
        return DATA_LAKE / "news"

    # Model cache
    @property
    def models_dir(self) -> Path:
        p = BASE_DIR / "models"
        p.mkdir(exist_ok=True)
        return p


settings = Settings()
