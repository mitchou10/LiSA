"""Best-effort Redis pub/sub used to tell workers that a profile changed."""

from __future__ import annotations

import contextlib
import json
import logging

from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("lisa.events")


async def publish_profile_changed(service_key: str, version: int) -> None:
    """Notify subscribers that ``service_key`` now has a new active version.

    Never raises: workers also refresh on a timer, so a lost message only
    delays propagation.
    """
    client = Redis.from_url(settings.redis_url)
    try:
        await client.publish(
            settings.profile_channel,
            json.dumps({"service_key": service_key, "version": version}),
        )
    except Exception as exc:  # noqa: BLE001 - notification is best-effort
        logger.warning("Could not publish profile change: %s", exc)
    finally:
        with contextlib.suppress(Exception):
            await client.aclose()
