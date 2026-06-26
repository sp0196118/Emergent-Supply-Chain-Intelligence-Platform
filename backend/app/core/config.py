"""
App configuration.

Centralizes environment-driven settings so later phases (MLflow URI, RL
checkpoint path, etc.) just add a field here instead of scattering env
lookups through the codebase.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "Supply Chain Digital Twin"
    cors_origins: list[str] = [
        "http://localhost:5173",  # Vite dev server (Phase 7)
        "http://localhost:3000",
    ]
    mlflow_tracking_uri: str = "./mlruns"  # used starting Phase 9


@lru_cache
def get_settings() -> Settings:
    return Settings()
