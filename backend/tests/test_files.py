import pytest
from httpx import AsyncClient

from app.core import storage
from app.models.enums import UserRole


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    return {"Authorization": "Bearer test-service-token"}


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    """In-memory object store, so tests need no RustFS."""
    store: dict[str, bytes] = {}

    async def put(key, data, content_type="application/octet-stream"):
        store[key] = data

    async def get(key):
        if key not in store:
            raise storage.ObjectNotFoundError(key)
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
    assert meta["s3_key"] == f"uploads/{meta['id']}"
    assert list(fake_storage) == [meta["s3_key"]]
    assert len(fake_storage) == 1

    content = await client.get(f"/api/v1/files/{meta['id']}/content", headers=headers)
    assert content.status_code == 200
    assert content.content == b"hello"

    resp = await client.delete(f"/api/v1/files/{meta['id']}", headers=headers)
    assert resp.status_code == 204
    assert fake_storage == {}
    resp = await client.get(f"/api/v1/files/{meta['id']}", headers=headers)
    assert resp.status_code == 404


async def test_a_deleted_source_keeps_its_metadata_and_is_gone(
    client: AsyncClient, fake_storage
):
    headers = await _admin_headers(client)
    meta = (await _upload(client, headers)).json()
    fake_storage.clear()  # the parser read the file, then deleted it from storage

    assert (await client.get(f"/api/v1/files/{meta['id']}", headers=headers)).json()[
        "sha256"
    ] == meta["sha256"]
    resp = await client.get(f"/api/v1/files/{meta['id']}/content", headers=headers)
    assert resp.status_code == 410
    assert "deleted" in resp.json()["detail"]


async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/files", files={"file": ("a.txt", b"x")})
    assert resp.status_code == 401


async def test_upload_rejects_empty_and_too_large(client: AsyncClient, monkeypatch):
    headers = await _admin_headers(client)
    assert (await _upload(client, headers, data=b"")).status_code == 400

    from app.api.routes import files

    monkeypatch.setattr(files.settings, "max_upload_mb", 0.000001)
    assert (await _upload(client, headers, data=b"x" * 100)).status_code == 413


async def test_other_user_cannot_read(client: AsyncClient, login_as):
    admin = await _admin_headers(client)
    meta = (await _upload(client, admin)).json()

    login_as("bob", UserRole.USER)
    assert (await client.get(f"/api/v1/files/{meta['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/files/{meta['id']}/content")).status_code == 404

    # The owner still reads it: another identity, same file id, owner match.
    login_as("service", UserRole.USER)
    assert (await client.get(f"/api/v1/files/{meta['id']}")).status_code == 200
