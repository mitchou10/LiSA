"""Runtime configuration for the Safety service, read from the environment."""

from __future__ import annotations

import os

# Celery broker/result backend (Redis).
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery queue this worker consumes from.
CELERY_QUEUE: str = os.getenv("CELERY_QUEUE", "llm-guard-safety")

# LiSA backend base URL (for self-registration).
LISA_API_URL: str = os.getenv("LISA_API_URL", "http://localhost:8000")

# Scanners to enable (comma-separated). All enabled by default.
ENABLED_SCANNERS: str = os.getenv(
    "ENABLED_SCANNERS", "prompt_injection,toxicity,secrets"
)
