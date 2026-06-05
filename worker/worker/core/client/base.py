"""Base HTTP client shared by all route-specific clients."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 30.0


class ClientError(Exception):
    """Raised when the backend returns an error response."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class BaseClient:
    """Thin synchronous wrapper around ``httpx.Client``.

    Independent from the backend code base: it only speaks HTTP and knows
    nothing about the server's internal models.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_prefix: str = DEFAULT_API_PREFIX,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("LISA_API_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")
        self._service_token = os.getenv("LISA_SERVICE_TOKEN")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "BaseClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- url helpers -------------------------------------------------------
    def _url(self, path: str, *, prefixed: bool = True) -> str:
        base = f"{self.base_url}{self.api_prefix}" if prefixed else self.base_url
        return f"{base}/{path.lstrip('/')}"

    # -- request -----------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        prefixed: bool = True,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        url = self._url(path, prefixed=prefixed)
        headers = (
            {"Authorization": f"Bearer {self._service_token}"}
            if self._service_token
            else None
        )
        response = self._client.request(
            method,
            url,
            params={k: v for k, v in (params or {}).items() if v is not None},
            json=json,
            headers=headers,
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ClientError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()
