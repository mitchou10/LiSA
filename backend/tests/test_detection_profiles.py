import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, async_session_factory, engine
from app.main import app
from app.models.enums import UserRole
from app.schemas.auth import UserCreate
from app.services.detection_profile import DetectionProfileService
from app.services.user import UserService

URL = "/api/v1/detection-profiles/gliner-ner"


@pytest.fixture
def published(monkeypatch):
    """Capture pub/sub notifications instead of talking to Redis."""
    calls: list[tuple[str, int]] = []

    async def fake(service_key: str, version: int) -> None:
        calls.append((service_key, version))

    monkeypatch.setattr("app.services.detection_profile.publish_profile_changed", fake)
    return calls


@pytest.fixture
async def client(published):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await UserService(session).ensure_admin("admin", "admin")
        await UserService(session).create(
            UserCreate(username="bob", password="bobpass1", role=UserRole.USER)
        )
        await DetectionProfileService(session).ensure_defaults()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def _headers(client: AsyncClient, username="admin", password="admin"):
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _config(**overrides):
    cfg = {
        "threshold": 0.4,
        "entities": [
            {"label": "iban", "category": "pii", "severity": "high", "action": "block"}
        ],
    }
    cfg.update(overrides)
    return cfg


async def test_seeded_default_is_version_1(client):
    headers = await _headers(client)
    resp = await client.get(URL, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"]["version"] == 1
    assert body["active"]["is_active"] is True
    labels = {e["label"] for e in body["active"]["config"]["entities"]}
    assert {"person", "API key"} <= labels


async def test_seed_is_idempotent(client):
    async with async_session_factory() as session:
        await DetectionProfileService(session).ensure_defaults()
    resp = await client.get(URL + "/versions", headers=await _headers(client))
    assert resp.json()["total"] == 1


async def test_create_version_becomes_active(client, published):
    headers = await _headers(client)
    resp = await client.post(
        URL + "/versions",
        json={"config": _config(), "comment": "add iban"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["version"] == 2
    assert body["created_by"] == "admin"
    # Category is normalized, missing fields get defaults.
    assert body["config"]["entities"][0]["category"] == "PII"
    assert body["config"]["entities"][0]["enabled"] is True
    assert published == [("gliner-ner", 2)]

    active = (await client.get(URL, headers=headers)).json()["active"]
    assert active["version"] == 2

    versions = (await client.get(URL + "/versions", headers=headers)).json()
    assert [v["version"] for v in versions["items"]] == [2, 1]
    assert [v["is_active"] for v in versions["items"]] == [True, False]


async def test_versions_are_immutable_snapshots(client):
    headers = await _headers(client)
    await client.post(URL + "/versions", json={"config": _config()}, headers=headers)
    v1 = (await client.get(URL + "/versions/1", headers=headers)).json()
    assert len(v1["config"]["entities"]) > 1


async def test_rollback_creates_new_version(client, published):
    headers = await _headers(client)
    await client.post(URL + "/versions", json={"config": _config()}, headers=headers)
    resp = await client.post(URL + "/versions/1/activate", headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 3
    assert body["comment"] == "Rollback to v1"
    v1 = (await client.get(URL + "/versions/1", headers=headers)).json()
    assert body["config"] == v1["config"]
    assert published[-1] == ("gliner-ner", 3)


@pytest.mark.parametrize(
    "config",
    [
        {"threshold": 2, "entities": []},
        {"entities": [{"label": " ", "category": "PII"}]},
        {"entities": [{"label": "a", "category": "PII", "severity": "extreme"}]},
        {
            "entities": [
                {"label": "Email", "category": "PII"},
                {"label": "email", "category": "PII"},
            ]
        },
    ],
)
async def test_invalid_config_rejected(client, config, published):
    resp = await client.post(
        URL + "/versions", json={"config": config}, headers=await _headers(client)
    )
    assert resp.status_code == 422
    assert published == []


async def test_unknown_profile_and_version(client):
    headers = await _headers(client)
    assert (
        await client.get("/api/v1/detection-profiles/nope", headers=headers)
    ).status_code == 404
    assert (await client.get(URL + "/versions/99", headers=headers)).status_code == 404
    assert (
        await client.post(URL + "/versions/99/activate", headers=headers)
    ).status_code == 404


async def test_requires_authentication(client):
    assert (await client.get(URL)).status_code == 401
    resp = await client.post(URL + "/versions", json={"config": _config()})
    assert resp.status_code == 401


async def test_non_admin_can_read_but_not_write(client):
    headers = await _headers(client, "bob", "bobpass1")
    assert (await client.get(URL, headers=headers)).status_code == 200
    resp = await client.post(URL + "/versions", json={"config": _config()}, headers=headers)
    assert resp.status_code == 403
