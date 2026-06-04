"""Client for the ``/health`` route."""

from __future__ import annotations

from typing import Any

from worker.core.client.base import BaseClient


class HealthClient(BaseClient):
    """Calls the backend liveness/readiness probe."""

    def check(self) -> dict[str, Any]:
        """GET /health -> {"status": "ok", "database": "ok"}."""
        return self._request("GET", "/health", prefixed=False)
