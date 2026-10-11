"""Runtime configuration for the parser service, read from the environment."""

from __future__ import annotations

import os

# Celery broker/result backend (Redis).
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery queue this worker consumes from.
CELERY_QUEUE: str = os.getenv("CELERY_QUEUE", "liteparse-ocr")

# LiSA backend base URL (for self-registration and task updates).
LISA_API_URL: str = os.getenv("LISA_API_URL", "http://localhost:8000")

# Tesseract language(s), "+"-separated (e.g. "eng+fra").
OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "eng+fra")

# Safety limits.
MAX_FILE_MB: float = float(os.getenv("MAX_FILE_MB", "10"))
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "50"))

# Blur applied to page images when asked (Gaussian radius, in pixels):
# max(BLUR_MIN_RADIUS, smallest image side * BLUR_RATIO).
BLUR_MIN_RADIUS: float = float(os.getenv("BLUR_MIN_RADIUS", "20"))
BLUR_RATIO: float = float(os.getenv("BLUR_RATIO", "0.03"))

# Delete the source file from object storage once it has been parsed, so only
# the extracted text / boxes / screenshots remain.
DELETE_SOURCE_AFTER_PARSE: bool = os.getenv(
    "DELETE_SOURCE_AFTER_PARSE", "true"
).lower() in ("1", "true", "yes")
