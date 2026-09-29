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
def parse(input_data: Any, task_id: str | None = None) -> dict[str, Any]:
    """Parse the uploaded files and return pages with text and boxes."""
    return get_service().process(input_data, task_id=task_id)
