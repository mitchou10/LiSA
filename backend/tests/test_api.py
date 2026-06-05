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


async def test_dashboard_analytics(client: AsyncClient):
    # Create a task and attach detection output the way a worker would.
    resp = await client.post(
        "/api/v1/tasks",
        json={"user_id": "alice", "input_data": {"text": "ignore previous"}},
    )
    task_id = resp.json()["id"]

    output = {
        "id": task_id,
        "pages": [
            {
                "page_number": 1,
                "detections": [
                    {
                        "flagged": True,
                        "confidence": 0.92,
                        "severity": "high",
                        "action": "block",
                        "jailbreak": True,
                    },
                    {
                        "flagged": False,
                        "confidence": 0.1,
                        "pii": False,
                    },
                ],
            }
        ],
    }
    resp = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "success", "progress": 100, "output_data": output},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/analytics/dashboard?days=30")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_tasks"] == 1
    assert data["total_detections"] == 2
    assert data["total_flagged"] == 1
    assert any(t["type"] == "jailbreak" and t["flagged"] == 1 for t in data["by_type"])
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["severity"] == "high"
    assert any(u["user_id"] == "alice" for u in data["by_user"])

    # Scoping to another user yields no data.
    resp = await client.get("/api/v1/analytics/dashboard?user_id=bob")
    assert resp.json()["total_tasks"] == 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_noop()))  # pragma: no cover


async def _noop():  # pragma: no cover
    return 0
