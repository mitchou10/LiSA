"""Celery tasks for the parser service."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.celery_app import celery_app
from app.service import ParserService


@lru_cache(maxsize=1)
def get_service() -> ParserService:
    """Return a process-wide singleton of the service."""
    return ParserService()


@celery_app.task(name=ParserService.name)
def parse(input_data: Any, task_id: str | None = None) -> None:
    """Parse the uploaded files and report pages with text and boxes through the API."""
    # Nothing is returned: the output goes back through the API, and what a task
    # returns is printed in the worker's log.
    get_service().process(input_data, task_id=task_id)
