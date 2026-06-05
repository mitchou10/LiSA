from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.keycloak import extract_roles, verify_keycloak_token
from app.core.security import decode_access_token
from app.database import get_session
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser
from app.services.analytics import AnalyticsService
from app.services.service import ServiceService
from app.services.task import TaskService
from app.services.user import UserService

settings = get_settings()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service_service(session: SessionDep) -> ServiceService:
    return ServiceService(session)


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(session)


def get_analytics_service(session: SessionDep) -> AnalyticsService:
    return AnalyticsService(session)


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


ServiceServiceDep = Annotated[ServiceService, Depends(get_service_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

# auto_error=False so we can return a clean 401 and support optional auth.
_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _resolve_user(
    creds: HTTPAuthorizationCredentials | None,
    users: UserService,
) -> CurrentUser | None:
    """Decode the bearer token (local or Keycloak) into a CurrentUser, if any."""
    if creds is None or not creds.credentials:
        return None
    token = creds.credentials

    # Machine-to-machine service token (worker / backend services).
    if settings.service_token and token == settings.service_token:
        return CurrentUser(
            id="service",
            username="service",
            role=UserRole.ADMIN,
            is_active=True,
        )

    if settings.auth_provider == "keycloak":
        try:
            claims = verify_keycloak_token(token)
        except jwt.PyJWTError:
            return None
        roles = extract_roles(claims)
        role = (
            UserRole.ADMIN if settings.keycloak_admin_role in roles else UserRole.USER
        )
        return CurrentUser(
            id=claims.get("sub", ""),
            username=claims.get("preferred_username")
            or claims.get("username")
            or claims.get("sub", ""),
            role=role,
        )

    # Local provider: validate our own JWT and confirm the account is active.
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None
    username = payload.get("username")
    if not username:
        return None
    user = await users.get_by_username(username)
    if user is None or not user.is_active:
        return None
    return CurrentUser(
        id=str(user.id),
        username=user.username,
        role=user.role,
        is_active=user.is_active,
    )


async def get_current_user(creds: BearerDep, users: UserServiceDep) -> CurrentUser:
    """Require a valid authenticated user."""
    user = await _resolve_user(creds, users)
    if user is None:
        raise _CREDENTIALS_EXC
    return user


def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Require an authenticated user with the admin role."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminDep = Annotated[CurrentUser, Depends(require_admin)]
