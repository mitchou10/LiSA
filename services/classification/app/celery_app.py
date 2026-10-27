"""Celery application for the Classification service.

The service self-registers against the LiSA backend once the worker is ready
(``worker_ready`` signal): if it already exists it is reused, otherwise it is
created.
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_ready
from worker.core.safe_logging import install_celery_safe_logging

from app.config import settings

logging.basicConfig(level=logging.INFO)
# Celery logs the value a task returns and the text of its errors: not here.
install_celery_safe_logging()
logger = logging.getLogger("lisa.service.classification")

celery_app = Celery(
    "classification",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Results go back through the API: nothing readable lingers in the Redis
    # result backend (the backend never reads Celery results).
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.CELERY_QUEUE,
)


@worker_ready.connect
def _register_service(**_kwargs: object) -> None:
    """Register the service with the backend when the worker comes up."""
    from app.tasks import get_service

    # In the background and with retries: the backend may not be up yet.
    try:
        get_service().register_in_background()
    except Exception as exc:  # noqa: BLE001 - never crash the worker on registration
        logger.warning("Service registration could not start: %s", exc)
