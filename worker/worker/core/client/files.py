"""Client for the ``/api/v1/files`` routes."""

from typing import Any

from worker.core.client.base import BaseClient


class FileClient(BaseClient):
    """Read and delete files the backend keeps in object storage."""

    def get(self, file_id: str) -> dict[str, Any]:
        """GET /files/{file_id} (metadata)."""
        return self._request("GET", f"/files/{file_id}")

    def download(self, file_id: str) -> bytes:
        """GET /files/{file_id}/content (raw bytes)."""
        return self._request("GET", f"/files/{file_id}/content", raw=True)

    def delete(self, file_id: str) -> None:
        """DELETE /files/{file_id}."""
        self._request("DELETE", f"/files/{file_id}")
