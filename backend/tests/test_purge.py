"""Purge the content of runs: on request, with an export, and after a delay."""

from datetime import UTC, datetime, timedelta

import pytest
from test_render import _file_run, _render, objects  # noqa: F401 (used below)

from app.core import storage
from app.database import async_session_factory
from app.services.privacy import purge_content, storage_keys
from app.services.purge import PurgeService

# The parser's page images, in storage, for every test here.
pytestmark = pytest.mark.usefixtures("objects")


@pytest.fixture
def deleted(monkeypatch):
    """The storage keys the purge removed."""
    keys: list[str] = []

    async def delete(key):
        keys.append(key)

    monkeypatch.setattr(storage, "delete_object", delete)
    return keys


def _url(run_id, suffix=""):
    return f"/api/v1/tasks/{run_id}{suffix}"


async def _outputs(client, headers, run_id):
    kids = (await client.get(_url(run_id, "/children"), headers=headers)).json()
    return {k["id"]: k for k in kids}


def test_purge_content_masks_the_words_and_keeps_the_numbers():
    value = {
        "pages": [
            {
                "page_number": 1,
                "content": "Maria Garcia",
                "filename": "contrat-garcia.pdf",
                "s3_key": "pages/t/1/1.png",
                "entities": [
                    {"label": "person", "text": "Maria", "score": 0.9, "start": 0}
                ],
            }
        ]
    }
    out = purge_content(value)
    page = out["pages"][0]
    assert page["content"] == "***** ******" and page["filename"] == "*" * len(
        "contrat-garcia.pdf"
    )
    assert page["s3_key"] is None
    assert page["entities"] == [
        {"label": "person", "text": "*****", "score": 0.9, "start": 0}
    ]
    assert storage_keys(value) == {"pages/t/1/1.png"}


async def test_purging_a_run_removes_what_the_documents_said(
    client,
    admin_headers,
    project,
    sent,
    deleted,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    await client.put(
        _url(run_id, "/replacements"),
        json={"text": "Maria Garcia", "replacement": "Client A"},
        headers=admin_headers,
    )
    purged = await client.post(_url(run_id, "/purge"), headers=admin_headers)
    assert purged.status_code == 200, purged.text
    assert purged.json()["purged_at"]

    run = (await client.get(_url(run_id), headers=admin_headers)).json()
    assert run["purged_at"].rstrip("Z") == purged.json()["purged_at"].rstrip("Z")
    kids = await _outputs(client, admin_headers, run_id)
    text = str([k["output_data"] for k in kids.values()])
    assert "Maria" not in text and "Garcia" not in text and "Paris" not in text
    assert "pages/t/1" not in text  # the image keys are gone
    # What the statistics are made of stays.
    entities = [
        e
        for k in kids.values()
        for page in (k["output_data"] or {}).get("pages", [])
        for e in page.get("entities", [])
    ]
    assert {e["label"] for e in entities} == {"person", "iban", "city"}
    assert all(e["flagged"] and e["bboxes"] for e in entities)
    # The page images are deleted from storage, the replacements dropped.
    assert {k for k in deleted if k.startswith("pages/")} == {
        "pages/t/1/1.png",
        "pages/t/1/2.png",
    }
    # ... and so is the uploaded file the run read.
    assert any(k.startswith("uploads/") for k in deleted)
    assert (
        await client.get(_url(run_id, "/replacements"), headers=admin_headers)
    ).json() == []
    # Nothing left to render.
    resp = await _render(client, admin_headers, run_id, page_numbers=[1], format="png")
    assert resp.status_code == 404 and "purged" in resp.json()["detail"]


async def test_purging_twice_changes_nothing(
    client,
    admin_headers,
    project,
    sent,
    deleted,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    first = (await client.post(_url(run_id, "/purge"), headers=admin_headers)).json()
    again = (await client.post(_url(run_id, "/purge"), headers=admin_headers)).json()
    assert first["purged_at"].rstrip("Z") == again["purged_at"].rstrip("Z")


async def test_only_the_owner_can_purge(
    client,
    admin_headers,
    project,
    sent,
    deleted,
    login_as,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    login_as("someone-else")
    resp = await client.post(_url(run_id, "/purge"))
    assert resp.status_code == 404
    kids = await _outputs(client, admin_headers, run_id)
    assert "Maria" in str([k["output_data"] for k in kids.values()])


async def test_an_export_can_purge_the_run_after_it(
    client,
    admin_headers,
    project,
    sent,
    deleted,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(
        client, admin_headers, run_id, page_numbers=[1], format="png", purge_after=True
    )
    assert resp.status_code == 200 and resp.content[:4] == b"\x89PNG"
    run = (await client.get(_url(run_id), headers=admin_headers)).json()
    assert run["purged_at"] is not None


async def test_runs_older_than_the_retention_are_purged(
    client,
    admin_headers,
    project,
    sent,
    deleted,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    async with async_session_factory() as session:
        # Retention is 7 days: a run finished just now is kept...
        assert await PurgeService(session).purge_expired() == 0
    async with async_session_factory() as session:
        # ... and purged once a week has gone by.
        later = datetime.now(UTC) + timedelta(days=8)
        assert await PurgeService(session).purge_expired(now=later) == 1
    async with async_session_factory() as session:
        assert await PurgeService(session).purge_expired(now=later) == 0
    run = (await client.get(_url(run_id), headers=admin_headers)).json()
    assert run["purged_at"] is not None


async def test_the_retention_is_public(client, admin_headers):
    resp = await client.get("/api/v1/retention", headers=admin_headers)
    assert resp.status_code == 200 and resp.json() == {"days": 7}
