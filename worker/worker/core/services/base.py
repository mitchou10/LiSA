"""Base class for worker services that self-register against the backend.

A concrete service declares its metadata (name, version, schemas, ...) and
implements :meth:`process`. On :meth:`register` it looks itself up on the
backend by name: if it already exists it is considered *up* and reused,
otherwise it is created.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from worker.core.client.services import ServiceClient
from worker.core.client.tasks import TaskClient

logger = logging.getLogger("lisa.worker.service")


class TaskStatus:
    """Task lifecycle states (mirrors the backend ``TaskStatus`` enum)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    REVOKED = "revoked"


class BaseService(ABC):
    """Abstract self-registering service.

    Subclasses override the class attributes and implement :meth:`process`::

        class MyGuard(BaseService):
            name = "my-guard"
            type = "guard"
            input_schema = {"type": "object", "properties": {"prompt": {"type": "string"}}}
            output_schema = {"type": "object", "properties": {"flagged": {"type": "boolean"}}}

            def process(self, input_data, task_id=None):
                return {"flagged": "ignore previous" in str(input_data).lower()}
    """

    # -- service metadata (override in subclasses) -------------------------
    name: str = ""
    version: str = "0.1.0"
    description: str | None = None
    tags: list[str] = []
    type: str = "other"  # "guard" | "analyser" | "other"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}

    def __init__(
        self,
        *,
        client: ServiceClient | None = None,
        tasks: TaskClient | None = None,
        base_url: str | None = None,
    ) -> None:
        if not self.name:
            raise ValueError(
                f"{type(self).__name__} must define a non-empty 'name' attribute."
            )
        self._client = client or ServiceClient(base_url)
        self._tasks = tasks or TaskClient(base_url)
        self._owns_client = client is None
        self.id: str | None = None

    # -- task progress / status -------------------------------------------
    def update_task(
        self,
        task_id: str | None,
        *,
        status: str | None = None,
        progress: int | None = None,
        output_data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """PATCH the backend task with new status/progress/output (best-effort).

        No-op when ``task_id`` is falsy (e.g. local runs / tests).
        """
        if not task_id:
            return
        payload: dict[str, Any] = {}
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = max(0, min(100, int(progress)))
        if output_data is not None:
            payload["output_data"] = output_data
        if error is not None:
            payload["error"] = error
        if not payload:
            return
        try:
            self._tasks.update(task_id, payload)
        except Exception as exc:  # noqa: BLE001 - never crash processing on reporting
            logger.warning("Failed to update task %s: %s", task_id, exc)

    # -- registration ------------------------------------------------------
    def definition(self) -> dict[str, Any]:
        """Build the ``ServiceCreate`` payload from the class metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tags": list(self.tags),
            "type": self.type,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    def register(self) -> dict[str, Any]:
        """Ensure the service exists on the backend.

        If a service with the same name already exists, it is reused and the
        method only reports that it is up. Otherwise it is created.
        """
        existing = self._client.find_by_name(self.name)
        if existing is not None:
            self.id = existing["id"]
            logger.info(
                "Service '%s' already registered (id=%s) — up.", self.name, self.id
            )
            return existing

        created = self._client.create(self.definition())
        self.id = created["id"]
        logger.info("Service '%s' registered (id=%s).", self.name, self.id)
        return created

    # -- processing --------------------------------------------------------
    @abstractmethod
    def process(self, input_data: Any, task_id: str | None = None) -> Any:
        """Run the service logic on ``input_data`` and return the result.

        Implementations should report progress/status via :meth:`update_task`
        when ``task_id`` is provided.
        """
        raise NotImplementedError

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()
            self._tasks.close()

    def __enter__(self) -> "BaseService":
        self.register()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
