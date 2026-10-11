"""Compute time: when a task started and ended, and the run as a whole."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

T = "/api/v1/tasks"
BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Freeze the clock the task service stamps with: ``clock(12.5)`` = 12.5 s in."""
    now = {"t": BASE}
    monkeypatch.setattr("app.services.task._now", lambda: now["t"])

    def at(seconds: float) -> None:
        now["t"] = BASE + timedelta(seconds=seconds)

    return at


async def _task(client, headers, **extra):
    resp = await client.post(
        T, json={"user_id": "u", "input_data": {}, **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _patch(client, headers, task_id, **body):
    resp = await client.patch(f"{T}/{task_id}", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_the_compute_time_runs_from_running_to_the_end(
    client: AsyncClient, admin_headers, clock
):
    task = await _task(client, admin_headers)
    assert task["started_at"] is None and task["duration_seconds"] is None
    clock(2)
    running = await _patch(client, admin_headers, task["id"], status="running")
    assert running["started_at"] is not None and running["duration_seconds"] is None
    clock(14.5)
    done = await _patch(
        client, admin_headers, task["id"], status="success", progress=100
    )
    assert done["duration_seconds"] == pytest.approx(12.5)
    got = (await client.get(f"{T}/{task['id']}", headers=admin_headers)).json()
    assert got["duration_seconds"] == pytest.approx(12.5)


async def test_the_start_is_not_moved_by_later_updates(client, admin_headers, clock):
    task = await _task(client, admin_headers)
    clock(1)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(5)
    await _patch(client, admin_headers, task["id"], progress=50)  # progress report
    await _patch(client, admin_headers, task["id"], status="running")
    clock(11)
    done = await _patch(client, admin_headers, task["id"], status="success")
    assert done["duration_seconds"] == pytest.approx(10)


async def test_the_wait_in_the_queue_is_not_compute_time(client, admin_headers, clock):
    task = await _task(client, admin_headers)  # created at t=0, waits 30 s
    clock(30)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(33)
    done = await _patch(client, admin_headers, task["id"], status="success")
    assert done["duration_seconds"] == pytest.approx(3)


async def test_an_error_ends_the_time_too(client, admin_headers, clock):
    task = await _task(client, admin_headers)
    clock(1)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(4)
    failed = await _patch(
        client, admin_headers, task["id"], status="error", error="boom"
    )
    assert failed["duration_seconds"] == pytest.approx(3)


async def test_a_task_that_never_ran_has_no_duration(client, admin_headers, clock):
    task = await _task(client, admin_headers)
    clock(5)
    done = await _patch(client, admin_headers, task["id"], status="success")
    assert done["finished_at"] is not None and done["started_at"] is None
    assert done["duration_seconds"] is None


async def test_revoking_ends_the_time(client, admin_headers, clock):
    task = await _task(client, admin_headers)
    clock(1)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(6)
    resp = await client.post(f"{T}/{task['id']}/revoke", headers=admin_headers)
    assert resp.json()["duration_seconds"] == pytest.approx(5)


async def test_a_retry_starts_the_clock_again(
    client, admin_headers, clock, monkeypatch
):
    monkeypatch.setattr("app.services.task.dispatch_task", lambda *a, **k: None)
    task = await _task(client, admin_headers)
    clock(1)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(3)
    await _patch(client, admin_headers, task["id"], status="error", error="x")
    retried = (
        await client.post(f"{T}/{task['id']}/retry", headers=admin_headers)
    ).json()
    assert retried["started_at"] is None and retried["finished_at"] is None
    clock(10)
    await _patch(client, admin_headers, task["id"], status="running")
    clock(17)
    done = await _patch(client, admin_headers, task["id"], status="success")
    assert done["duration_seconds"] == pytest.approx(7)


async def test_a_run_lasts_from_its_first_worker_to_its_last(
    client, admin_headers, clock
):
    parent = await _task(client, admin_headers)
    kids = [
        await _task(client, admin_headers, parent_task_id=parent["id"])
        for _ in range(2)
    ]
    clock(2)
    await _patch(client, admin_headers, kids[0]["id"], status="running")
    clock(3)
    await _patch(client, admin_headers, kids[1]["id"], status="running")
    clock(6)
    await _patch(client, admin_headers, kids[0]["id"], status="success", progress=100)
    mid = (await client.get(f"{T}/{parent['id']}", headers=admin_headers)).json()
    assert mid["started_at"] is not None
    assert mid["finished_at"] is None and mid["duration_seconds"] is None  # still going
    clock(9)
    await _patch(client, admin_headers, kids[1]["id"], status="success", progress=100)
    done = (await client.get(f"{T}/{parent['id']}", headers=admin_headers)).json()
    assert done["status"] == "success"
    assert done["duration_seconds"] == pytest.approx(7)  # 2 -> 9


async def test_a_waiting_task_that_fails_with_the_run_has_no_duration(
    client, admin_headers, clock, monkeypatch
):
    """Workers released by a parser that failed never ran: no time to report."""
    for name in ("liteparse-ocr", "ner"):
        await client.post(
            "/api/v1/services",
            json={"name": name, "queue": name, "type": "analyser"},
            headers=admin_headers,
        )
    monkeypatch.setattr("app.services.task.dispatch_task", lambda *a, **k: None)
    parent = await _task(client, admin_headers)
    parser = await _task(client, admin_headers, parent_task_id=parent["id"])
    waiter = await _task(
        client,
        admin_headers,
        parent_task_id=parent["id"],
        input_data={"awaiting": parser["id"]},
    )
    clock(1)
    await _patch(client, admin_headers, parser["id"], status="running")
    clock(2)
    await _patch(client, admin_headers, parser["id"], status="error", error="bad pdf")
    waiter = (await client.get(f"{T}/{waiter['id']}", headers=admin_headers)).json()
    assert waiter["status"] == "error"
    assert waiter["duration_seconds"] is None
    parent = (await client.get(f"{T}/{parent['id']}", headers=admin_headers)).json()
    assert parent["duration_seconds"] == pytest.approx(1)
