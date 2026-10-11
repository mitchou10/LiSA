"""S3-compatible object storage (RustFS). Blocking boto3 calls, run in threads."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings

settings = get_settings()

_bucket_ready = False


@lru_cache
def _client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        # RustFS is addressed by host:port, not by <bucket>.<host>.
        config=Config(s3={"addressing_style": "path"}),
    )


def _ensure_bucket() -> None:
    # Lazy: a network call at import time would run during test collection.
    global _bucket_ready
    if _bucket_ready:
        return
    try:
        _client().head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        _client().create_bucket(Bucket=settings.s3_bucket)
    _bucket_ready = True


def _put(key: str, data: bytes, content_type: str) -> None:
    _ensure_bucket()
    _client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
    )


def _get(key: str) -> bytes:
    return _client().get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()


def _delete(key: str) -> None:
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)


async def put_object(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    await asyncio.to_thread(_put, key, data, content_type)


async def get_object(key: str) -> bytes:
    return await asyncio.to_thread(_get, key)


async def delete_object(key: str) -> None:
    await asyncio.to_thread(_delete, key)
