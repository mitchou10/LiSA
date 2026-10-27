"""Celery tasks for the NER service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import NerService


@lru_cache(maxsize=1)
def get_service() -> NerService:
    """Return a process-wide singleton of the service (model loaded once)."""
    return NerService()


# The Celery task name matches the service name so the backend can dispatch by
# service name.
@celery_app.task(name=NerService.name)
def scan(input_data: Any, task_id: str | None = None) -> None:
    """Extract the entities of the pages of ``input_data``."""
    # Nothing is returned: the output goes back through the API, and what a task
    # returns is printed in the worker's log.
    get_service().process(input_data, task_id=task_id)
