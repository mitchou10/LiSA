"""Celery tasks for the relation extraction service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import RelationService


@lru_cache(maxsize=1)
def get_service() -> RelationService:
    """Return a process-wide singleton of the service (model loaded once)."""
    return RelationService()


# The Celery task name matches the service name so the backend can dispatch by
# service name.
@celery_app.task(name=RelationService.name)
def scan(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Extract the relations of the pages of ``input_data``."""
    return get_service().process(input_data, task_id=task_id)
