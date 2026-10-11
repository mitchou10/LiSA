import pytest
from httpx import AsyncClient

from app.core import storage
from app.models.enums import UserRole

PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture
def objects(monkeypatch):
    store: dict[str, bytes] = {"pages/t/1/1.png": PNG}

    async def get(key):
        if key not in store:
            raise storage.ObjectNotFoundError(key)
        return store[key]

    monkeypatch.setattr(storage, "get_object", get)
    return store


async def _parsed_task(client, headers, pages):
    task = (
        await client.post(
            "/api/v1/tasks",
            json={"user_id": "service", "input_data": {}},
            headers=headers,
        )
    ).json()
    resp = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "success", "output_data": {"pages": pages}},
        headers=headers,
    )
    assert resp.status_code == 200
    return task["id"]


PAGES = [
    {"page_number": 1, "s3_key": "pages/t/1/1.png"},
    {"page_number": 2, "s3_key": "pages/t/1/2.png"},  # object missing
    {"page_number": 3, "s3_key": None},  # no screenshot
]


async def test_the_owner_gets_the_screenshot(
    client: AsyncClient, admin_headers, objects
):
    task_id = await _parsed_task(client, admin_headers, PAGES)
    resp = await client.get(
        f"/api/v1/tasks/{task_id}/pages/1/image", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == PNG
    assert "private" in resp.headers["cache-control"]


async def test_unknown_or_screenshotless_pages_are_404(client, admin_headers, objects):
    task_id = await _parsed_task(client, admin_headers, PAGES)
    for n in (3, 9):
        resp = await client.get(
            f"/api/v1/tasks/{task_id}/pages/{n}/image", headers=admin_headers
        )
        assert resp.status_code == 404


async def test_a_deleted_image_is_gone(client, admin_headers, objects):
    task_id = await _parsed_task(client, admin_headers, PAGES)
    resp = await client.get(
        f"/api/v1/tasks/{task_id}/pages/2/image", headers=admin_headers
    )
    assert resp.status_code == 410


async def test_a_task_without_output_has_no_pages(client, admin_headers, objects):
    task = (
        await client.post(
            "/api/v1/tasks",
            json={"user_id": "service", "input_data": {}},
            headers=admin_headers,
        )
    ).json()
    resp = await client.get(
        f"/api/v1/tasks/{task['id']}/pages/1/image", headers=admin_headers
    )
    assert resp.status_code == 404


async def test_other_users_cannot_read_it_but_admins_can(
    client, admin_headers, objects, login_as
):
    task_id = await _parsed_task(client, admin_headers, PAGES)  # owned by "service"
    login_as("mallory", UserRole.USER)
    resp = await client.get(f"/api/v1/tasks/{task_id}/pages/1/image")
    assert resp.status_code == 404
    login_as("root", UserRole.ADMIN)
    assert (
        await client.get(f"/api/v1/tasks/{task_id}/pages/1/image")
    ).status_code == 200


async def test_requires_authentication(client, admin_headers, objects):
    task_id = await _parsed_task(client, admin_headers, PAGES)
    assert (
        await client.get(f"/api/v1/tasks/{task_id}/pages/1/image")
    ).status_code == 401
