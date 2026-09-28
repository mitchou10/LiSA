"""Celery tasks for the Safety service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import SafetyService


@lru_cache(maxsize=1)
def get_service() -> SafetyService:
    """Return a process-wide singleton of the service (models loaded once)."""
    return SafetyService()


@celery_app.task(name=SafetyService.name)
def scan(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Run the Safety scanners on ``input_data`` and return the result."""
    return get_service().process(input_data, task_id=task_id)
