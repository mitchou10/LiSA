"""Authorization Code + PKCE flow against Keycloak, driven by the backend (BFF)."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from redis.asyncio import Redis

from app.config import get_settings
from app.core.keycloak import extract_roles, verify_keycloak_token
from app.core.session import REFRESH_MARGIN_SECONDS, Session, SessionStore
from app.models.enums import UserRole

settings = get_settings()

_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore(
            Redis.from_url(settings.redis_url, decode_responses=True),
            settings.session_ttl_seconds,
        )
    return _store


def is_safe_internal_path(path: str) -> bool:
    """Only "/foo" is allowed; "//evil.com" or "https://evil.com" would turn the
    post-login redirect into an open redirect."""
    return path.startswith("/") and not path.startswith("//") and "\\" not in path


def build_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _public_realm_url() -> str:
    # Browser-facing: the in-network URL is usually unreachable from the browser.
    return (
        f"{settings.keycloak_server_url.rstrip('/')}/realms/{settings.keycloak_realm}"
    )


def authorization_url(state: str, code_challenge: str) -> str:
    query = urlencode(
        {
            "client_id": settings.keycloak_client_id,
            "response_type": "code",
            "redirect_uri": settings.oidc_callback_url,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{_public_realm_url()}/protocol/openid-connect/auth?{query}"


def end_session_url(id_token: str | None) -> str:
    query = urlencode(
        {
            "client_id": settings.keycloak_client_id,
            "post_logout_redirect_uri": settings.frontend_url,
            **({"id_token_hint": id_token} if id_token else {}),
        }
    )
    return f"{_public_realm_url()}/protocol/openid-connect/logout?{query}"


async def _token_request(data: dict) -> dict:
    payload = {
        "client_id": settings.keycloak_client_id,
        **(
            {"client_secret": settings.keycloak_client_secret}
            if settings.keycloak_client_secret
            else {}
        ),
        **data,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.keycloak_token_base}/protocol/openid-connect/token",
            data=payload,
        )
    response.raise_for_status()
    return response.json()


async def exchange_code(code: str, code_verifier: str) -> dict:
    return await _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oidc_callback_url,
            "code_verifier": code_verifier,
        }
    )


async def revoke_refresh_token(refresh_token: str) -> None:
    payload = {
        "client_id": settings.keycloak_client_id,
        **(
            {"client_secret": settings.keycloak_client_secret}
            if settings.keycloak_client_secret
            else {}
        ),
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{settings.keycloak_token_base}/protocol/openid-connect/logout",
            data=payload,
        )


def identity_from_access_token(access_token: str) -> dict | None:
    """Validated identity (signature, issuer, audience) as a plain dict."""
    try:
        claims = verify_keycloak_token(access_token)
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    if not sub:
        return None
    roles = extract_roles(claims)
    role = UserRole.ADMIN if settings.keycloak_admin_role in roles else UserRole.USER
    return {
        "id": sub,
        "username": claims.get("preferred_username") or claims.get("username") or sub,
        "role": role.value,
    }


async def load_session(session_id: str) -> Session | None:
    """Fetch a session, transparently refreshing its tokens when near expiry."""
    store = get_session_store()
    session = await store.get_raw(session_id)
    if session is None:
        return None
    if session.expires_at - REFRESH_MARGIN_SECONDS > time.time():
        return session
    try:
        tokens = await _token_request(
            {"grant_type": "refresh_token", "refresh_token": session.refresh_token}
        )
    except httpx.HTTPError:
        await store.delete(session_id)
        return None
    identity = identity_from_access_token(tokens["access_token"])
    if identity is None:
        await store.delete(session_id)
        return None
    session.identity = identity
    session.access_token = tokens["access_token"]
    session.refresh_token = tokens["refresh_token"]
    session.expires_at = time.time() + tokens["expires_in"]
    session.id_token = tokens.get("id_token", session.id_token)
    await store.save(session_id, session)
    return session
