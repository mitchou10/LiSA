"""Celery tasks for the GLiNER service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import GlinerService


@lru_cache(maxsize=1)
def get_service() -> GlinerService:
    """Return a process-wide singleton of the service (model loaded once)."""
    return GlinerService()


@celery_app.task(name=GlinerService.name)
def scan(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Run the GLiNER scanner on ``input_data`` and return the result."""
    return get_service().process(input_data, task_id=task_id)
