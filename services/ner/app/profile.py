"""Live detection profile: fetched from the backend, refreshed on push.

The backend publishes ``{"service_key", "version"}`` on a Redis channel when an
admin saves a new profile version. A daemon thread listens on that channel and
swaps the in-memory profile, so changes apply without restarting the worker. A
periodic refresh covers lost messages, and the environment-based defaults are
used whenever the backend cannot be reached.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("lisa.service.ner.profile")

Profile = dict[str, Any]  # {"version", "threshold", "entities": [...]}


class ProfileProvider:
    """Hold the current profile and keep it fresh in the background.

    ``fetch`` returns ``(version, config)``; without it the provider is static
    and always answers with ``fallback()``.
    """

    def __init__(
        self,
        *,
        service_key: str,
        fallback: Callable[[], Profile],
        fetch: Callable[[], tuple[int, dict[str, Any]]] | None = None,
        redis_url: str | None = None,
        channel: str = "lisa:detection-profiles",
        refresh_seconds: float = 300.0,
    ) -> None:
        self.service_key = service_key
        self._fallback = fallback
        self._fetch = fetch
        self._redis_url = redis_url
        self._channel = channel
        self._refresh_seconds = refresh_seconds
        self._lock = threading.Lock()
        self._profile: Profile | None = None
        self._thread: threading.Thread | None = None
        self._thread_pid: int | None = None

    # -- public ------------------------------------------------------------
    def get(self) -> Profile:
        """Return the current profile (remote, else last known, else default)."""
        if self._fetch is None:
            return self._fallback()
        self._ensure_listener()
        with self._lock:
            current = self._profile
        if current is None:
            self.refresh()
            with self._lock:
                current = self._profile
        return current or self._fallback()

    def refresh(self) -> bool:
        """Fetch the active version now. Keeps the previous one on failure."""
        if self._fetch is None:
            return False
        try:
            version, config = self._fetch()
        except Exception as exc:  # noqa: BLE001 - keep serving the last profile
            logger.warning("Could not fetch detection profile: %s", exc)
            return False
        profile: Profile = {
            "version": version,
            "threshold": float(config.get("threshold", 0.5)),
            "entities": list(config.get("entities", [])),
        }
        with self._lock:
            previous = self._profile["version"] if self._profile else None
            self._profile = profile
        if previous != version:
            logger.info(
                "Detection profile '%s' now at v%s (%d entities)",
                self.service_key,
                version,
                len(profile["entities"]),
            )
        return True

    # -- background listener ------------------------------------------------
    def _ensure_listener(self) -> None:
        """Start the listener thread in *this* process (safe after fork)."""
        if not self._redis_url:
            return
        pid = os.getpid()
        if self._thread is not None and self._thread_pid == pid:
            return
        self._thread_pid = pid
        self._thread = threading.Thread(
            target=self._listen, name="profile-listener", daemon=True
        )
        self._thread.start()

    def _matches(self, raw: Any) -> bool:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return False
        return isinstance(data, dict) and data.get("service_key") == self.service_key

    def _listen(self) -> None:
        import redis

        while True:
            try:
                client = redis.Redis.from_url(self._redis_url)
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(self._channel)
                # Catch anything published while we were disconnected.
                self.refresh()
                while True:
                    message = pubsub.get_message(timeout=self._refresh_seconds)
                    if message is None:
                        self.refresh()  # periodic safety net
                    elif self._matches(message.get("data")):
                        self.refresh()
            except Exception as exc:  # noqa: BLE001 - reconnect forever
                logger.warning("Profile listener error: %s (retrying)", exc)
                time.sleep(5)
