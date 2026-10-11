"""Runtime configuration of the image classification service, read from the environment."""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # Celery broker/result backend (Redis). Both default to REDIS_URL.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_QUEUE: str = "image-classification"

    # LiSA backend base URL (self-registration and task updates).
    LISA_API_URL: str = "http://localhost:8000"

    # Classifier implementation (see app.classifiers.BACKENDS) and the model it
    # loads. CLIP is English-only: write the descriptions in English.
    IMAGE_BACKEND: str = "clip"
    IMAGE_MODEL: str = "openai/clip-vit-base-patch32"

    # What CLIP is asked to match with the image for a label that has no
    # description. {label} is the label name.
    IMAGE_PROMPT_TEMPLATE: str = "a photo of {label}"

    # Multi-label: a label is returned when its probability reaches this (a
    # classification can override it).
    IMAGE_THRESHOLD: float = 0.3

    # Largest image accepted, in MB.
    MAX_IMAGE_MB: float = 20.0

    # Object storage the images are read from (the parser's bucket).
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    @model_validator(mode="after")
    def _default_celery_urls(self) -> Settings:
        self.CELERY_BROKER_URL = self.CELERY_BROKER_URL or self.REDIS_URL
        self.CELERY_RESULT_BACKEND = self.CELERY_RESULT_BACKEND or self.REDIS_URL
        return self


settings = Settings()
