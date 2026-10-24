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
def sent(monkeypatch):
    """Capture what is sent to the broker: (service, task_id, input, queue)."""
    calls: list[tuple[str, str, dict, str | None]] = []

    def fake(service_name, task_id, input_data, queue=None):
        calls.append((service_name, task_id, input_data, queue))

    monkeypatch.setattr("app.services.task.dispatch_task", fake)
    return calls


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    from app.core import storage

    async def put(key, data, content_type="application/octet-stream"):
        pass

    monkeypatch.setattr(storage, "put_object", put)


@pytest.fixture
def login_as():
    """Act as another identity from now on (cleared with the client)."""

    def _login(user_id: str, role: UserRole = UserRole.USER) -> None:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=user_id, username=user_id, role=role
        )

    return _login


# The services the runs dispatch to (see app.services.run).
RUN_SERVICES = {
    "liteparse-ocr": "liteparse-ocr",
    "ner": "ner",
    "relation": "relation",
    "classification": "classification",
    "safety": "safety",
    "anonymize-v2": "anonymize-v2",
    "image-classification": "image-classification",
}


@pytest.fixture
async def registered(client, admin_headers):
    """The workers have registered themselves."""
    for name, queue in RUN_SERVICES.items():
        resp = await client.post(
            "/api/v1/services",
            json={"name": name, "queue": queue, "type": "analyser"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


@pytest.fixture
async def project(client, admin_headers, registered):
    """A project that looks for everything."""
    pid = (
        await client.post(
            "/api/v1/projects", json={"name": "Docs"}, headers=admin_headers
        )
    ).json()["id"]
    # Drop the definitions seeded at creation: this project adds its own.
    for kind in ("entities", "safety"):
        for row in (
            await client.get(f"/api/v1/projects/{pid}/{kind}", headers=admin_headers)
        ).json():
            resp = await client.delete(
                f"/api/v1/projects/{pid}/{kind}/{row['id']}", headers=admin_headers
            )
            assert resp.status_code == 204, resp.text

    async def add(kind, payload):
        resp = await client.post(
            f"/api/v1/projects/{pid}/{kind}", json=payload, headers=admin_headers
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return {
        "id": pid,
        "iban": await add(
            "entities",
            {
                "label": "iban",
                "description": "A bank account",
                "category": "pii",
                "severity": "high",
                "action": "block",
                "threshold": 0.8,
            },
        ),
        "old": await add("entities", {"label": "legacy", "enabled": False}),
        "works_for": await add(
            "relations", {"name": "works_for", "description": "person -> organization"}
        ),
        "doc_type": await add(
            "classifications",
            {
                "name": "doc_type",
                "labels": [{"name": "invoice", "description": "A bill"}, "other"],
            },
        ),
        "jailbreak": await add(
            "safety",
            {
                "name": "jailbreak",
                "multi_label": True,
                "threshold": 0.4,
                "labels": ["prompt_injection", {"name": "benign", "is_ok": True}],
            },
        ),
    }
