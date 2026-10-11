"""Shared test setup.

Authentication is Keycloak only, so tests do not log in: the admin is the
service account (service token), and other identities are simulated with
``login_as``, which overrides the current-user dependency.
"""

import os

SERVICE_TOKEN = "test-service-token"

# Must be set before the app (and its settings) are imported.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SERVICE_TOKEN"] = SERVICE_TOKEN

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.database import Base, engine
from app.main import app
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """The service account: an admin identity."""
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


@pytest.fixture
def login_as():
    """Act as another identity from now on (cleared with the client)."""

    def _login(user_id: str, role: UserRole = UserRole.USER) -> None:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=user_id, username=user_id, role=role
        )

    return _login
