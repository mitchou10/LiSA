from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    app_name: str = "LiSA API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # PostgreSQL (async driver)
    database_url: str = "postgresql+asyncpg://lisa:lisa@db:5432/lisa"
    db_echo: bool = False

    # CORS
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
