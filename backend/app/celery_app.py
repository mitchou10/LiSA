"""Celery client used by the API to dispatch work to worker services.

The backend never *executes* tasks; it only *sends* them to the broker. Each
worker service registers a Celery task whose **name equals the service name**
(see ``services/*/app/tasks.py``), so dispatching is simply::

    celery_app.send_task(service_name, args=[input_data, task_id])
"""

from __future__ import annotations

from typing import Any

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lisa-backend",
    broker=settings.broker_url,
    backend=settings.result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


def dispatch_task(
    service_name: str,
    task_id: str,
    input_data: dict[str, Any],
    queue: str | None = None,
) -> None:
    """Send a task to the worker that owns ``service_name``.

    The Celery task name matches the service name, and the worker's task
    signature is ``(input_data, task_id)`` so it can report progress/status
    back to the API. The message is routed to ``queue`` (defaulting to the
    service name) so heterogeneous workers never receive tasks they cannot
    handle.
    """
    celery_app.send_task(
        service_name,
        args=[input_data, task_id],
        queue=queue or service_name,
    )
