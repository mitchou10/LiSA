"""Celery tasks for the Anonymize service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import AnonymizeServiceV2


@lru_cache(maxsize=1)
def get_service() -> AnonymizeServiceV2:
    """Return a process-wide singleton of the service (models loaded once)."""
    return AnonymizeServiceV2()


# The Celery task name matches the service name so the backend can dispatch by
# service name (``celery.send_task(service.name, ...)``).
@celery_app.task(name=AnonymizeServiceV2.name)
def scan(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Run the Anonymize scanner on ``input_data`` and return the result.

    ``task_id`` is the backend task to report progress/status against.
    """
    return get_service().process(input_data, task_id=task_id)
