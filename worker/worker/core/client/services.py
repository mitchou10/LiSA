"""Client for the ``/api/v1/services`` routes."""

from typing import Any

from worker.core.client.base import BaseClient


class ServiceClient(BaseClient):
    """CRUD operations on services."""

    def list(
        self,
        *,
        q: str | None = None,
        type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """GET /services (paginated); returns the page items."""
        page = self._request(
            "GET",
            "/services",
            params={"q": q, "type": type, "limit": limit, "offset": offset},
        )
        if isinstance(page, dict):
            return page.get("items", [])
        return page or []

    def find_by_name(self, name: str) -> dict[str, Any] | None:
        """Return the service with the given exact name, or ``None``."""
        results = self.list(q=name)
        return next((s for s in results if s.get("name") == name), None)

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
