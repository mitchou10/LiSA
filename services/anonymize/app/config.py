"""Runtime configuration for the Anonymize service, read from the environment."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_QUEUE: str = os.getenv("CELERY_QUEUE", "llm-guard-anonymize")
    LISA_API_URL: str = os.getenv("LISA_API_URL", "http://localhost:8000")
    ANONYMIZE_THRESHOLD: float = float(os.getenv("ANONYMIZE_THRESHOLD", "0"))
    ANONYMIZE_LANGUAGE: str = os.getenv("ANONYMIZE_LANGUAGE", "en")
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET", "")
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", "")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_ENDPOINT_URL: str = os.getenv("AWS_S3_ENDPOINT_URL", "")
    # Gaussian blur radius for page images, in pixels:
    # max(BLUR_MIN_RADIUS, smallest image side * BLUR_RATIO).
    BLUR_MIN_RADIUS: float = float(os.getenv("BLUR_MIN_RADIUS", "20"))
    BLUR_RATIO: float = float(os.getenv("BLUR_RATIO", "0.03"))


settings = Settings()

# Celery broker/result backend (Redis).
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery queue this worker consumes from. Must match what the backend routes
# to (the backend routes by the service's ``queue``, defaulting to its name).
CELERY_QUEUE: str = os.getenv("CELERY_QUEUE", "llm-guard-anonymize")

# LiSA backend base URL (for self-registration).
LISA_API_URL: str = os.getenv("LISA_API_URL", "http://localhost:8000")

# llm-guard Anonymize scanner tuning.
ANONYMIZE_THRESHOLD: float = float(os.getenv("ANONYMIZE_THRESHOLD", "0"))
ANONYMIZE_LANGUAGE: str = os.getenv("ANONYMIZE_LANGUAGE", "en")
