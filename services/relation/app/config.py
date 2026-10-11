"""Runtime configuration of the relation extraction service, read from the environment."""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # Celery broker/result backend (Redis). Both default to REDIS_URL.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_QUEUE: str = "relation"

    # LiSA backend base URL (self-registration and task updates).
    LISA_API_URL: str = "http://localhost:8000"

    # Extractor implementation (see app.extractors.BACKENDS) and the model it
    # loads. The multilingual GLiNER2.5 checkpoint by default.
    RELATION_BACKEND: str = "gliner2"
    RELATION_MODEL: str = "fastino/gliner2.5-multi-v1"

    # Confidence below which a relation is dropped (a relation can override it).
    RELATION_THRESHOLD: float = 0.5

    # Long context: a page is scanned in overlapping windows counted in
    # whitespace words (GLiNER2 ``extract_long``). Both ends of a relation must
    # fall in the same window, so raise the overlap if relations spanning a long
    # distance are missed.
    CHUNK_SIZE: int = 384
    CHUNK_OVERLAP: int = 128

    @model_validator(mode="after")
    def _check_chunking(self) -> Settings:
        if not 0 <= self.CHUNK_OVERLAP < self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP must be >= 0 and < CHUNK_SIZE.")
        return self

    @model_validator(mode="after")
    def _default_celery_urls(self) -> Settings:
        self.CELERY_BROKER_URL = self.CELERY_BROKER_URL or self.REDIS_URL
        self.CELERY_RESULT_BACKEND = self.CELERY_RESULT_BACKEND or self.REDIS_URL
        return self


settings = Settings()
