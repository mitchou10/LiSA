import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import storage
from app.database import Base, async_session_factory, engine
from app.main import app
from app.models.enums import UserRole
from app.schemas.auth import UserCreate
from app.services.user import UserService


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await UserService(session).ensure_admin("admin", "admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, "admin", "admin")


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    """In-memory object store, so tests need no RustFS."""
    store: dict[str, bytes] = {}

    async def put(key, data, content_type="application/octet-stream"):
        store[key] = data

    async def get(key):
        return store[key]

    async def delete(key):
        store.pop(key, None)

    monkeypatch.setattr(storage, "put_object", put)
    monkeypatch.setattr(storage, "get_object", get)
    monkeypatch.setattr(storage, "delete_object", delete)
    return store


async def _upload(client: AsyncClient, headers, data=b"hello", name="a.txt"):
    return await client.post(
        "/api/v1/files",
        files={"file": (name, data, "text/plain")},
        headers=headers,
    )


async def test_upload_read_delete(client: AsyncClient, fake_storage):
    headers = await _admin_headers(client)
    resp = await _upload(client, headers)
    assert resp.status_code == 201, resp.text
    meta = resp.json()
    assert meta["filename"] == "a.txt"
    assert meta["size"] == 5
    assert len(meta["sha256"]) == 64
    assert len(fake_storage) == 1

    content = await client.get(f"/api/v1/files/{meta['id']}/content", headers=headers)
    assert content.status_code == 200
    assert content.content == b"hello"

    resp = await client.delete(f"/api/v1/files/{meta['id']}", headers=headers)
    assert resp.status_code == 204
    assert fake_storage == {}
    resp = await client.get(f"/api/v1/files/{meta['id']}", headers=headers)
    assert resp.status_code == 404


async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/files", files={"file": ("a.txt", b"x")})
    assert resp.status_code == 401


async def test_upload_rejects_empty_and_too_large(client: AsyncClient, monkeypatch):
    headers = await _admin_headers(client)
    assert (await _upload(client, headers, data=b"")).status_code == 400

    from app.api.routes import files

    monkeypatch.setattr(files.settings, "max_upload_mb", 0.000001)
    assert (await _upload(client, headers, data=b"x" * 100)).status_code == 413


async def test_other_user_cannot_read(client: AsyncClient):
    admin = await _admin_headers(client)
    meta = (await _upload(client, admin)).json()

    async with async_session_factory() as session:
        await UserService(session).create(
            UserCreate(username="bob", password="bobpass", role=UserRole.USER)
        )
    bob = await _login(client, "bob", "bobpass")

    assert (
        await client.get(f"/api/v1/files/{meta['id']}", headers=bob)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/files/{meta['id']}/content", headers=bob)
    ).status_code == 404
