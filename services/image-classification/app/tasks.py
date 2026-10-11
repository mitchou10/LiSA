"""Celery tasks for the image classification service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import ImageClassificationService


@lru_cache(maxsize=1)
def get_service() -> ImageClassificationService:
    """Return a process-wide singleton of the service (model loaded once)."""
    return ImageClassificationService()


# The Celery task name matches the service name so the backend can dispatch by
# service name.
@celery_app.task(name=ImageClassificationService.name)
def classify_images(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Classify the images of ``input_data`` and return the labels per image."""
    return get_service().process(input_data, task_id=task_id)
