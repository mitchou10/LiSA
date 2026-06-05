from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import UserCreate
from app.services.exceptions import ConflictError


class UserService:
    """Business logic for user accounts and credential checks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def get_by_username(self, username: str) -> User | None:
        return await self.repo.get_by_username(username)

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.repo.get_by_username(username)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def create(self, data: UserCreate) -> User:
        if await self.repo.get_by_username(data.username) is not None:
            raise ConflictError(f"User '{data.username}' already exists.")
        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        user = await self.repo.add(user)
        await self.session.commit()
        return user

    async def ensure_admin(
        self, username: str, password: str, email: str | None = None
    ) -> User:
        """Seed the default admin account if it does not already exist."""
        existing = await self.repo.get_by_username(username)
        if existing is not None:
            return existing
        admin = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        admin = await self.repo.add(admin)
        await self.session.commit()
        return admin
