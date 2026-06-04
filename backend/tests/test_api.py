import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

# Use a shared in-memory SQLite database across the async connections.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _event_loop_policy():
    yield


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_service_crud(client: AsyncClient):
    payload = {
        "name": "guard",
        "type": "guard",
        "tags": ["security"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    resp = await client.post("/api/v1/services", json=payload)
    assert resp.status_code == 201, resp.text
    svc = resp.json()
    assert svc["name"] == "guard"

    resp = await client.get(f"/api/v1/services/{svc['id']}")
    assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/services/{svc['id']}", json={"description": "updated"}
    )
    assert resp.json()["description"] == "updated"


async def test_task_lifecycle(client: AsyncClient):
    resp = await client.post(
        "/api/v1/tasks",
        json={"user_id": "u1", "input_data": {"text": "hello"}},
    )
    assert resp.status_code == 201, resp.text
    task = resp.json()
    task_id = task["id"]
    assert task["status"] == "pending"

    # update progress / mark error
    resp = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "error", "error": "boom", "progress": 50},
    )
    assert resp.json()["status"] == "error"

    # status endpoint
    resp = await client.get(f"/api/v1/tasks/{task_id}/status")
    assert resp.json()["progress"] == 50

    # retry
    resp = await client.post(f"/api/v1/tasks/{task_id}/retry")
    assert resp.json()["status"] == "pending"

    # revoke
    resp = await client.post(f"/api/v1/tasks/{task_id}/revoke")
    assert resp.json()["status"] == "revoked"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_noop()))  # pragma: no cover


async def _noop():  # pragma: no cover
    return 0
