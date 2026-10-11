"""Runtime configuration of the NER service, read from the environment."""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # Celery broker/result backend (Redis). Both default to REDIS_URL.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_QUEUE: str = "ner"

    # LiSA backend base URL (self-registration, task updates, detection profile).
    LISA_API_URL: str = "http://localhost:8000"

    # Extractor implementation (see app.extractors.BACKENDS) and the model it
    # loads. The multilingual GLiNER2.5 checkpoint by default.
    NER_BACKEND: str = "gliner2"
    NER_MODEL: str = "fastino/gliner2.5-multi-v1"

    # Confidence below which an entity is dropped (a label can override it).
    NER_THRESHOLD: float = 0.5

    # Long context: a page is scanned in overlapping windows counted in
    # whitespace words (GLiNER2 ``extract_long``). Raise the overlap if entities
    # are often cut at a window boundary.
    CHUNK_SIZE: int = 384
    CHUNK_OVERLAP: int = 64

    # -- Live detection profile (labels, categories, actions edited in LiSA) --
    PROFILE_ENABLED: bool = True
    # Key of this service's profile on the backend.
    PROFILE_KEY: str = "gliner-ner"
    # Redis pub/sub channel the backend publishes to when a profile changes.
    PROFILE_CHANNEL: str = "lisa:detection-profiles"
    # Safety-net refresh period (seconds) in case a message is missed.
    PROFILE_REFRESH_SECONDS: float = 300.0

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
