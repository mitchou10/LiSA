import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUserDep, UserServiceDep
from app.config import get_settings
from app.core import oidc
from app.core.security import create_access_token
from app.core.session import PendingAuth
from app.schemas.auth import CurrentUser, LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

LOGIN_RATE_LIMIT = 20
LOGIN_RATE_WINDOW_SECONDS = 60


def _require_keycloak() -> None:
    if settings.auth_provider != "keycloak":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get("/config")
async def auth_config() -> dict:
    """Tell the frontend which login flow to present."""
    return {"provider": settings.auth_provider}


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, users: UserServiceDep) -> Token:
    """Local provider: username/password -> JWT access token."""
    if settings.auth_provider != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    user = await users.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user.id, username=user.username, role=user.role.value
    )
    return Token(access_token=token)


@router.get("/login")
async def oidc_login(request: Request, redirect: str = "/") -> RedirectResponse:
    """Keycloak (BFF): redirect the browser to the realm login page."""
    _require_keycloak()
    store = oidc.get_session_store()
    client_ip = request.client.host if request.client else "unknown"
    if not await store.check_rate_limit(
        f"login:{client_ip}", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts.",
        )
    next_path = redirect if oidc.is_safe_internal_path(redirect) else "/"
    verifier, challenge = oidc.build_pkce_pair()
    state = secrets.token_urlsafe(32)
    await store.save_pending(
        state, PendingAuth(code_verifier=verifier, next_path=next_path)
    )
    return RedirectResponse(
        oidc.authorization_url(state, challenge),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/callback")
async def oidc_callback(code: str, state: str) -> RedirectResponse:
    """Keycloak (BFF): exchange the code server-side and open a session."""
    _require_keycloak()
    store = oidc.get_session_store()
    pending = await store.pop_pending(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired login attempt.",
        )
    try:
        tokens = await oidc.exchange_code(code, pending.code_verifier)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Login failed."
        ) from error
    identity = oidc.identity_from_access_token(tokens["access_token"])
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve identity.",
        )
    session_id = await store.create_session(identity, tokens)
    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}{pending.next_path}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """End the BFF session and return the Keycloak end-session URL."""
    _require_keycloak()
    origin = request.headers.get("origin")
    if origin is None or origin.rstrip("/") != settings.frontend_url.rstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request rejected.",
        )
    store = oidc.get_session_store()
    session_id = request.cookies.get(settings.session_cookie_name)
    id_token: str | None = None
    if session_id:
        session = await store.get_raw(session_id)
        if session:
            id_token = session.id_token
            try:
                await oidc.revoke_refresh_token(session.refresh_token)
            except httpx.HTTPError:
                pass
        await store.delete(session_id)
    response.delete_cookie(settings.session_cookie_name)
    return {"redirectUrl": oidc.end_session_url(id_token)}


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUserDep) -> CurrentUser:
    """Return the identity of the currently authenticated user."""
    return user
