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

    # Celery / Redis (task dispatch to worker services)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # CORS
    cors_origins: list[str] = ["*"]

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
