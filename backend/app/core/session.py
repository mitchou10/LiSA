"""Server-side BFF sessions stored in Redis.

The browser only ever holds an opaque session id in an HttpOnly cookie; the
Keycloak tokens never leave the backend.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

PENDING_PREFIX = "lisa:auth:pending:"
SESSION_PREFIX = "lisa:auth:session:"
RATE_LIMIT_PREFIX = "lisa:auth:rate:"
PENDING_TTL_SECONDS = 600
# Refresh slightly before expiry so a request never races a dying token.
REFRESH_MARGIN_SECONDS = 30


@dataclass
class PendingAuth:
    code_verifier: str
    next_path: str


@dataclass
class Session:
    identity: dict
    access_token: str
    refresh_token: str
    expires_at: float
    # Needed for a silent RP-initiated logout (id_token_hint).
    id_token: str | None = None


class SessionStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    async def save_pending(self, state: str, pending: PendingAuth) -> None:
        await self._redis.set(
            f"{PENDING_PREFIX}{state}",
            json.dumps(asdict(pending)),
            ex=PENDING_TTL_SECONDS,
        )

    async def pop_pending(self, state: str) -> PendingAuth | None:
        raw = await self._redis.getdel(f"{PENDING_PREFIX}{state}")
        return PendingAuth(**json.loads(raw)) if raw else None

    async def create_session(self, identity: dict, tokens: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        session = Session(
            identity=identity,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=time.time() + tokens["expires_in"],
            id_token=tokens.get("id_token"),
        )
        await self.save(session_id, session)
        return session_id

    async def save(self, session_id: str, session: Session) -> None:
        await self._redis.set(
            f"{SESSION_PREFIX}{session_id}",
            json.dumps(asdict(session)),
            ex=self._ttl_seconds,
        )

    async def get_raw(self, session_id: str) -> Session | None:
        raw = await self._redis.get(f"{SESSION_PREFIX}{session_id}")
        return Session(**json.loads(raw)) if raw else None

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(f"{SESSION_PREFIX}{session_id}")

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """True if the call is allowed, False once the limit is hit."""
        redis_key = f"{RATE_LIMIT_PREFIX}{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        return count <= limit
