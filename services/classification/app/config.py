"""Runtime configuration of the classification service, read from the environment."""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # Celery broker/result backend (Redis). Both default to REDIS_URL.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_QUEUE: str = "classification"

    # LiSA backend base URL (self-registration and task updates).
    LISA_API_URL: str = "http://localhost:8000"

    # Which classifier implementation to use (see app.classifiers.BACKENDS) and
    # which model it loads. Swap either one without touching the service.
    CLASSIFIER_BACKEND: str = "gliner2"
    CLASSIFIER_MODEL: str = "fastino/gliner2.5-multi-v1"

    # Default score a label must reach in multi-label mode (a task can override it).
    CLASSIFIER_THRESHOLD: float = 0.4

    # Long context (GLiNER2 ``classify_text_long``): a page is scanned in
    # overlapping windows counted in whitespace words, and the per-window
    # scores are merged (the most confident prediction wins). Raise the overlap
    # if what you look for often sits across a window boundary.
    CLASSIFIER_CHUNK_SIZE: int = 384
    CLASSIFIER_CHUNK_OVERLAP: int = 64

    @model_validator(mode="after")
    def _check_chunking(self) -> Settings:
        if not 0 <= self.CLASSIFIER_CHUNK_OVERLAP < self.CLASSIFIER_CHUNK_SIZE:
            raise ValueError(
                "CLASSIFIER_CHUNK_OVERLAP must be >= 0 and < CLASSIFIER_CHUNK_SIZE."
            )
        return self

    @model_validator(mode="after")
    def _default_celery_urls(self) -> Settings:
        self.CELERY_BROKER_URL = self.CELERY_BROKER_URL or self.REDIS_URL
        self.CELERY_RESULT_BACKEND = self.CELERY_RESULT_BACKEND or self.REDIS_URL
        return self


settings = Settings()
