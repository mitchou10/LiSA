from pydantic import BaseModel

from app.models.enums import UserRole


class CurrentUser(BaseModel):
    """Identity attached to a request: a Keycloak user or the service account."""

    id: str
    username: str
    role: UserRole
    is_active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
