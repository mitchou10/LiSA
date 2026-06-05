from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=4, max_length=255)
    email: str | None = None
    role: UserRole = UserRole.USER


class CurrentUser(BaseModel):
    """Identity attached to a request, from a local or Keycloak token."""

    id: str
    username: str
    role: UserRole
    is_active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
