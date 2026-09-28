"""Runtime configuration for the GLiNER service, read from the environment."""

from __future__ import annotations

import os

# Celery broker/result backend (Redis).
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery queue this worker consumes from.
CELERY_QUEUE: str = os.getenv("CELERY_QUEUE", "gliner-ner")

# LiSA backend base URL (for self-registration).
LISA_API_URL: str = os.getenv("LISA_API_URL", "http://localhost:8000")

# HuggingFace model to use (multilingual by default).
GLINER_MODEL: str = os.getenv("GLINER_MODEL", "gliner-community/gliner_small-v2.5")

# Detection threshold (0-1). Lower = more detections, higher = more precise.
GLINER_THRESHOLD: float = float(os.getenv("GLINER_THRESHOLD", "0.5"))

# Comma-separated list of entity labels to detect.
# These are the "zero-shot" labels GLiNER will search for in the text.
GLINER_LABELS: str = os.getenv(
    "GLINER_LABELS",
    ",".join([
        # PII
        "person",
        "email address",
        "phone number",
        "physical address",
        "date of birth",
        "national ID",
        # Police / Justice
        "police report",
        "police officer",
        "suspect",
        "victim",
        "witness",
        "criminal record",
        "investigation information",
        "evidence",
        # Santé
        "medical information",
        "medical record",
        "medical diagnosis",
        "medical history",
        "medication",
        "prescription",
        # Juridique
        "legal information",
        "court case",
        "court decision",
        "lawsuit",
        "legal proceeding",
        "lawyer",
        "judge",
        "prosecutor",
        # Secrets
        "password",
        "API key",
        "access token",
        "private key",
    ]),
)
