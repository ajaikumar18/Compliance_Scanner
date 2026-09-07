"""
Application configuration – loaded from environment variables / .env file.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find the .env file – search up from this file's location
_THIS_DIR = Path(__file__).resolve().parent          # app/core/
_BACKEND_DIR = _THIS_DIR.parent.parent               # backend/
_WORKSPACE_DIR = _BACKEND_DIR.parent                 # e:/compliance-scanner/

# Pick the first .env that actually exists
_ENV_FILE = next(
    (str(p) for p in [_BACKEND_DIR / ".env", _WORKSPACE_DIR / ".env"] if p.exists()),
    ".env",  # fallback – let pydantic-settings try itself
)

class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Object Storage (MinIO) ────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"

    # ── Auth ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── AI ────────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""          # Optional; not used in live scan path (OpenRouter is primary)
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT: float = 12.0  # Seconds; gemini-2.5-flash averages ~2.5s

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "labelGuard AI"
    APP_VERSION: str = "3.0.1"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
