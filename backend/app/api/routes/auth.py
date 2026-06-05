from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, UserServiceDep
from app.core.security import create_access_token
from app.schemas.auth import CurrentUser, LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, users: UserServiceDep) -> Token:
    """Authenticate with username/password and receive a JWT access token."""
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


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUserDep) -> CurrentUser:
    """Return the identity of the currently authenticated user."""
    return user
