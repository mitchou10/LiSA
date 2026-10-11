"""HTTP clients calling the LiSA backend routes.

Each client targets one route group and is fully independent from the
backend code base (no shared imports — only HTTP).

Usage::

    from worker.core.client import LisaClient

    with LisaClient("http://localhost:8000") as lisa:
        print(lisa.health.check())
        services = lisa.services.list()
        task = lisa.tasks.submit({"user_id": "worker", "input_data": {...}})
"""

from __future__ import annotations

import httpx

from worker.core.client.base import BaseClient, ClientError
from worker.core.client.detection_profiles import DetectionProfileClient
from worker.core.client.files import FileClient
from worker.core.client.health import HealthClient
from worker.core.client.services import ServiceClient
from worker.core.client.tasks import TaskClient

__all__ = [
    "BaseClient",
    "ClientError",
    "DetectionProfileClient",
    "FileClient",
    "HealthClient",
    "LisaClient",
    "ServiceClient",
    "TaskClient",
]


class LisaClient:
    """Aggregate facade exposing every route-specific client.

    A single underlying ``httpx.Client`` is shared so connections are reused.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_prefix: str = "/api/v1",
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        kwargs = {"base_url": base_url, "api_prefix": api_prefix, "client": self._http}
        self.health = HealthClient(**kwargs)
        self.services = ServiceClient(**kwargs)
        self.tasks = TaskClient(**kwargs)
        self.files = FileClient(**kwargs)
        self.detection_profiles = DetectionProfileClient(**kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> LisaClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
