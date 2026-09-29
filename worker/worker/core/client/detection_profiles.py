"""Client for the ``/api/v1/detection-profiles`` routes."""

from __future__ import annotations

from typing import Any

from worker.core.client.base import BaseClient


class DetectionProfileClient(BaseClient):
    """Read the editable detection settings of a service."""

    def get(self, service_key: str) -> dict[str, Any]:
        """GET /detection-profiles/{service_key} (profile + active version)."""
        return self._request("GET", f"/detection-profiles/{service_key}")

    def get_active_config(self, service_key: str) -> tuple[int, dict[str, Any]]:
        """Return ``(version, config)`` of the currently active version."""
        active = self.get(service_key)["active"]
        return int(active["version"]), active["config"]
