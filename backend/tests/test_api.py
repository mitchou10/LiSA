import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from httpx import ASGITransport, AsyncClient

# Use a shared in-memory SQLite database across the async connections.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from app.database import Base, engine
from app.main import app


@pytest.fixture(scope="module", autouse=True)
def _event_loop_policy():
    yield


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Seed the default admin (lifespan is not triggered by ASGITransport).
    from app.database import async_session_factory
    from app.services.user import UserService

    async with async_session_factory() as session:
        await UserService(session).ensure_admin("admin", "admin")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_auth_login_and_me(client: AsyncClient):
    # Wrong password is rejected.
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "nope"}
    )
    assert resp.status_code == 401

    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


async def test_protected_requires_auth(client: AsyncClient):
    # Everything except /health now requires auth: anonymous submit is rejected.
    resp = await client.post(
        "/api/v1/tasks", json={"user_id": "anon", "input_data": {"text": "hi"}}
    )
    assert resp.status_code == 401

    # Listing all tasks and the dashboard also require auth.
    assert (await client.get("/api/v1/tasks")).status_code == 401
    assert (await client.get("/api/v1/analytics/dashboard")).status_code == 401

    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/tasks",
        json={"user_id": "anon", "input_data": {"text": "hi"}},
        headers=headers,
    )
    assert resp.status_code == 201
    assert (await client.get("/api/v1/tasks", headers=headers)).status_code == 200
    assert (
        await client.get("/api/v1/analytics/dashboard", headers=headers)
    ).status_code == 200


async def test_service_token_grants_machine_access(client: AsyncClient):
    # The worker authenticates with the configured service token.
    from app.config import get_settings

    settings = get_settings()
    settings.service_token = "worker-secret"
    try:
        headers = {"Authorization": "Bearer worker-secret"}
        resp = await client.post(
            "/api/v1/tasks",
            json={"user_id": "svc", "input_data": {"text": "hi"}},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
    finally:
        settings.service_token = None


async def test_service_crud(client: AsyncClient):
    payload = {
        "name": "guard",
        "type": "guard",
        "tags": ["security"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    headers = await _admin_headers(client)
    resp = await client.post("/api/v1/services", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    svc = resp.json()
    assert svc["name"] == "guard"

    resp = await client.get(f"/api/v1/services/{svc['id']}", headers=headers)
    assert resp.status_code == 200

    # Reads require auth too: anonymous is rejected.
    resp = await client.get(f"/api/v1/services/{svc['id']}")
    assert resp.status_code == 401

    # Mutations require admin: anonymous is rejected.
    resp = await client.patch(
        f"/api/v1/services/{svc['id']}", json={"description": "nope"}
    )
    assert resp.status_code == 401

    resp = await client.patch(
        f"/api/v1/services/{svc['id']}",
        json={"description": "updated"},
        headers=headers,
    )
    assert resp.json()["description"] == "updated"


async def test_task_lifecycle(client: AsyncClient):
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/tasks",
        json={"user_id": "u1", "input_data": {"text": "hello"}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task = resp.json()
    task_id = task["id"]
    assert task["status"] == "pending"

    # update progress / mark error
    resp = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "error", "error": "boom", "progress": 50},
        headers=headers,
    )
    assert resp.json()["status"] == "error"

    # status endpoint
    resp = await client.get(f"/api/v1/tasks/{task_id}/status", headers=headers)
    assert resp.json()["progress"] == 50

    # retry / revoke require admin.
    resp = await client.post(f"/api/v1/tasks/{task_id}/retry", headers=headers)
    assert resp.json()["status"] == "pending"

    resp = await client.post(f"/api/v1/tasks/{task_id}/revoke", headers=headers)
    assert resp.json()["status"] == "revoked"


async def test_dashboard_analytics(client: AsyncClient):
    # Create a task and attach detection output the way a worker would.
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/tasks",
        json={"user_id": "alice", "input_data": {"text": "ignore previous"}},
        headers=headers,
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
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/analytics/dashboard?days=30", headers=headers)
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
    resp = await client.get("/api/v1/analytics/dashboard?user_id=bob", headers=headers)
    assert resp.json()["total_tasks"] == 0
