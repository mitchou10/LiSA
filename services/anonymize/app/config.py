"""Runtime configuration for the Anonymize service, read from the environment."""

from __future__ import annotations

import os

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
