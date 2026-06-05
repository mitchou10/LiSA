"""Client for the ``/api/v1/tasks`` routes."""

from typing import Any

from worker.core.client.base import BaseClient


class TaskClient(BaseClient):
    """Submit and manage tasks, including revoke/retry."""

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /tasks."""
        return self._request("POST", "/tasks", json=payload)

    def list_all(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """GET /tasks (paginated); returns the page items."""
        page = self._request(
            "GET",
            "/tasks",
            params={"user_id": user_id, "limit": limit, "offset": offset},
        )
        if isinstance(page, dict):
            return page.get("items", [])
        return page or []

    def get(self, task_id: str) -> dict[str, Any]:
        """GET /tasks/{task_id}."""
        return self._request("GET", f"/tasks/{task_id}")

    def status(self, task_id: str) -> dict[str, Any]:
        """GET /tasks/{task_id}/status."""
        return self._request("GET", f"/tasks/{task_id}/status")

    def children(self, task_id: str) -> list[dict[str, Any]]:
        """GET /tasks/{task_id}/children."""
        return self._request("GET", f"/tasks/{task_id}/children")

    def update(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """PATCH /tasks/{task_id}."""
        return self._request("PATCH", f"/tasks/{task_id}", json=payload)

    def revoke(self, task_id: str) -> dict[str, Any]:
        """POST /tasks/{task_id}/revoke."""
        return self._request("POST", f"/tasks/{task_id}/revoke")

    def retry(self, task_id: str) -> dict[str, Any]:
        """POST /tasks/{task_id}/retry."""
        return self._request("POST", f"/tasks/{task_id}/retry")

    def delete(self, task_id: str) -> None:
        """DELETE /tasks/{task_id}."""
        self._request("DELETE", f"/tasks/{task_id}")
