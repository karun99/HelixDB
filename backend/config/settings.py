"""HelixDB runtime configuration.

Follows the S-AI convention: a config-defaults file merged with environment
overrides (.env). Kept dependency-light using stdlib + pydantic-settings.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "helixdb.db"
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_SCORING = CONFIG_DIR / "scoring_config.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HELIXDB_", env_file=".env", extra="ignore")

    app_name: str = "HelixDB"
    version: str = "1.0.0"
    secret_key: str = "helixdb-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Database connectivity (SRS section 32). `enabled=False` => mock/local data.
    db_enabled: bool = False
    db_api_base_url: str = "/api"
    db_name: str = "researchmitra"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    mock_auth: bool = True


settings = Settings()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "backups").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)


def load_default_scoring() -> dict[str, Any]:
    import json

    if DEFAULT_SCORING.exists():
        try:
            return json.loads(DEFAULT_SCORING.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}
