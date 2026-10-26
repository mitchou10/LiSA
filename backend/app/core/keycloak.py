"""Optional Keycloak/OIDC bearer-token validation.

Enabled by setting ``AUTH_PROVIDER=keycloak`` together with the
``KEYCLOAK_*`` settings. Tokens are verified against the realm's JWKS endpoint.
The admin role is derived from the realm/client roles embedded in the token.
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.config import get_settings

settings = get_settings()


@lru_cache
def _jwks_client() -> PyJWKClient:
    if not settings.keycloak_jwks_url:
        raise RuntimeError("Keycloak is not configured (missing server/realm).")
    return PyJWKClient(settings.keycloak_jwks_url)


def verify_keycloak_token(token: str) -> dict:
    """Validate a Keycloak access token and return its claims.

    Raises ``jwt.PyJWTError`` if the token is invalid or expired.
    """
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.keycloak_issuer,
        options={"verify_aud": False},
    )


def extract_roles(claims: dict) -> set[str]:
    """Collect realm and client roles from a Keycloak token payload."""
    roles: set[str] = set()
    realm_access = claims.get("realm_access") or {}
    roles.update(realm_access.get("roles", []))
    resource_access = claims.get("resource_access") or {}
    for resource in resource_access.values():
        if isinstance(resource, dict):
            roles.update(resource.get("roles", []))
    return roles
