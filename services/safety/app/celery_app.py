"""Celery application for the Safety service.

The service self-registers against the LiSA backend once the worker is ready
(``worker_ready`` signal): if it already exists it is reused, otherwise it is
created.
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_ready

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lisa.service.safety")

celery_app = Celery(
    "safety",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.CELERY_QUEUE,
)


@worker_ready.connect
def _register_service(**_kwargs: object) -> None:
    """Register the service with the backend when the worker comes up."""
    from app.tasks import get_service

    try:
        get_service().register()
    except Exception as exc:  # noqa: BLE001 - never crash the worker on registration
        logger.warning("Service registration failed: %s", exc)
