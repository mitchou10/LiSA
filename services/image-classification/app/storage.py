"""Object storage the images are read from."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.errors import ImageClassificationError


class Storage:
    """Thin wrapper around a boto3 S3 client, scoped to ``S3_BUCKET``."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        """Built on first use, so the service runs without S3 configured."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                aws_access_key_id=settings.S3_ACCESS_KEY or None,
                aws_secret_access_key=settings.S3_SECRET_KEY or None,
                region_name=settings.S3_REGION or None,
                endpoint_url=settings.S3_ENDPOINT_URL or None,
            )
        return self._client

    @staticmethod
    def require_configured() -> None:
        if not settings.S3_BUCKET:
            raise ImageClassificationError(
                "Object storage is not configured (S3_BUCKET)."
            )

    def read(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=settings.S3_BUCKET, Key=key)
            return obj["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise ImageClassificationError(
                f"Cannot fetch '{key}' from storage: {exc}"
            ) from exc
