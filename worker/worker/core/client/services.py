"""Client for the ``/api/v1/services`` routes."""

from __future__ import annotations

from typing import Any

from worker.core.client.base import BaseClient


class ServiceClient(BaseClient):
    """CRUD operations on services."""

    def list(
        self, *, name: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """GET /services (optionally filtered by exact name)."""
        return self._request(
            "GET",
            "/services",
            params={"name": name, "limit": limit, "offset": offset},
        )

    def find_by_name(self, name: str) -> dict[str, Any] | None:
        """Return the service with the given name, or ``None``."""
        results = self.list(name=name)
        return results[0] if results else None

    def get(self, service_id: str) -> dict[str, Any]:
        """GET /services/{service_id}."""
        return self._request("GET", f"/services/{service_id}")

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /services."""
        return self._request("POST", "/services", json=payload)

    def update(self, service_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """PATCH /services/{service_id}."""
        return self._request("PATCH", f"/services/{service_id}", json=payload)

    def delete(self, service_id: str) -> None:
        """DELETE /services/{service_id}."""
        self._request("DELETE", f"/services/{service_id}")
