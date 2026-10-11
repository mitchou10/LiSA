"""Runtime configuration of the parser service, read from the environment."""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # Celery broker/result backend (Redis). Both default to REDIS_URL.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    # Queue this worker consumes from.
    CELERY_QUEUE: str = "liteparse-ocr"

    # LiSA backend base URL (self-registration and task updates).
    LISA_API_URL: str = "http://localhost:8000"

    # Tesseract language(s), "+"-separated (e.g. "eng+fra").
    OCR_LANGUAGE: str = "eng+fra"

    # Safety limits.
    MAX_FILE_MB: float = 10.0
    MAX_PAGES: int = 50

    # Blur the page screenshots by default (override per task with the
    # ``blur_screenshots`` input). Gaussian radius, in pixels:
    # max(BLUR_MIN_RADIUS, smallest image side * BLUR_RATIO).
    BLUR_SCREENSHOTS: bool = True
    # Calibrated on a 150 dpi A4 page (1240 px wide): a radius of ~8 px keeps the
    # layout (lines, blocks, tables) visible while the text is unreadable, even
    # to OCR (3 px is still partly legible). The radius follows the page width.
    BLUR_MIN_RADIUS: float = 4.0
    BLUR_RATIO: float = 0.007

    # Delete the source file from the bucket as soon as it has been read, so
    # only the extracted text / boxes / screenshots remain.
    DELETE_SOURCE_AFTER_PARSE: bool = True

    # Object storage: sources are read from, and page screenshots written to,
    # this bucket (required to process a task).
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
