"""The dashboard reads the current services' outputs, with compute times."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.enums import UserRole

P = "/api/v1/projects"
BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("app.services.task.dispatch_task", lambda *a, **k: None)


@pytest.fixture
def clock(monkeypatch):
    now = {"t": BASE}
    monkeypatch.setattr("app.services.task._now", lambda: now["t"])

    def at(seconds: float) -> None:
        now["t"] = BASE + timedelta(seconds=seconds)

    return at


@pytest.fixture
async def project(client: AsyncClient, admin_headers):
    for name in ("ner", "safety"):
        await client.post(
            "/api/v1/services",
            json={"name": name, "queue": name, "type": "analyser"},
            headers=admin_headers,
        )
    body = (
        await client.post(P, json={"name": "Contracts"}, headers=admin_headers)
    ).json()
    pid = body["id"]
    # The seeded PII entities are kept: the ner step has work to do.
    await client.post(
        f"{P}/{pid}/safety",
        json={"name": "jailbreak", "labels": [{"name": "safe", "is_ok": True}, "bad"]},
        headers=admin_headers,
    )
    return pid


def entity(category, severity, action, score):
    return {
        "id": "e",
        "label": "x",
        "category": category,
        "text": "t",
        "score": score,
        "severity": severity,
        "action": action,
        "flagged": action != "allow",
    }


async def finish_run(client, headers, project_id, clock, *, ner_time=10, safety_time=4):
    """A run whose workers report outputs and take the given times."""
    run = (
        await client.post(f"{P}/{project_id}/runs", json={"text": "x"}, headers=headers)
    ).json()
    steps = {s["step"]: s["task_id"] for s in run["steps"]}

    async def patch(task_id, **body):
        resp = await client.patch(
            f"/api/v1/tasks/{task_id}", json=body, headers=headers
        )
        assert resp.status_code == 200, resp.text

    clock(0)
    await patch(steps["ner"], status="running")
    clock(ner_time)
    await patch(
        steps["ner"],
        status="success",
        output_data={
            "pages": [
                {
                    "page_number": 1,
                    "entities": [
                        entity("PII", "high", "block", 0.97),
                        entity("PII", "medium", "redact", 0.8),
                        entity("ORG", "low", "allow", 0.9),
                    ],
                }
            ]
        },
    )
    await patch(steps["safety"], status="running")  # starts when ner is done
    clock(ner_time + safety_time)
    await patch(
        steps["safety"],
        status="success",
        output_data={
            "pages": [
                {
                    "page_number": 1,
                    "safety": [
                        {
                            "name": "jailbreak",
                            "flagged": True,
                            "labels": [{"label": "bad", "score": 0.7, "flagged": True}],
                        }
                    ],
                }
            ]
        },
    )
    return run


async def dashboard(client, headers, query=""):
    resp = await client.get(f"/api/v1/analytics/dashboard{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_entities_and_safety_checks_are_detections(
    client, admin_headers, project, clock
):
    await finish_run(client, admin_headers, project, clock)
    data = await dashboard(client, admin_headers)
    # 3 entities + 1 safety check; the "allow" entity is found but not flagged.
    assert data["total_detections"] == 4 and data["total_flagged"] == 3
    types = {t["type"]: t for t in data["by_type"]}
    assert types["entity:PII"] == {"type": "entity:PII", "total": 2, "flagged": 2}
    assert types["entity:ORG"]["flagged"] == 0
    assert types["safety:jailbreak"]["flagged"] == 1
    sev = {s["severity"]: s["count"] for s in data["by_severity"]}
    assert sev == {"high": 2, "medium": 1}  # a safety hit counts as high
    alerts = {(a["type"], a["severity"]) for a in data["alerts"]}
    assert alerts == {
        ("entity:PII", "high"),
        ("entity:PII", "medium"),
        ("safety:jailbreak", "high"),
    }


async def test_runs_and_their_compute_time(client, admin_headers, project, clock):
    await finish_run(client, admin_headers, project, clock, ner_time=10, safety_time=4)
    data = await dashboard(client, admin_headers)
    assert data["total_runs"] == 1 and data["runs_failed"] == 0
    # From the first worker's start (0 s) to the last one's end (14 s).
    assert data["avg_run_seconds"] == pytest.approx(14)


async def test_the_time_of_each_service(client, admin_headers, project, clock):
    await finish_run(client, admin_headers, project, clock, ner_time=10, safety_time=4)
    await finish_run(client, admin_headers, project, clock, ner_time=20, safety_time=6)
    by = {
        s["service"]: s for s in (await dashboard(client, admin_headers))["by_service"]
    }
    assert by["ner"]["tasks"] == 2 and by["ner"]["timed"] == 2
    assert by["ner"]["avg_seconds"] == pytest.approx(15)
    assert by["ner"]["max_seconds"] == pytest.approx(20)
    assert by["ner"]["total_seconds"] == pytest.approx(30)
    assert by["safety"]["avg_seconds"] == pytest.approx(5)
    order = [
        s["service"] for s in (await dashboard(client, admin_headers))["by_service"]
    ]
    assert order == ["ner", "safety"]  # where the compute time goes, most first


async def test_a_failed_task_counts_as_an_error_without_a_time(
    client, admin_headers, project, clock
):
    run = (
        await client.post(
            f"{P}/{project}/runs", json={"text": "x"}, headers=admin_headers
        )
    ).json()
    ner = next(s["task_id"] for s in run["steps"] if s["step"] == "ner")
    await client.patch(
        f"/api/v1/tasks/{ner}",
        json={"status": "error", "error": "boom"},
        headers=admin_headers,
    )
    by = {
        s["service"]: s for s in (await dashboard(client, admin_headers))["by_service"]
    }
    assert by["ner"]["errors"] == 1 and by["ner"]["timed"] == 0
    assert by["ner"]["avg_seconds"] == 0.0


async def test_projects_are_compared(client, admin_headers, project, clock):
    await finish_run(client, admin_headers, project, clock)
    (stat,) = (await dashboard(client, admin_headers))["by_project"]
    assert stat["name"] == "Contracts" and stat["runs"] == 1
    assert stat["detections"] == 4 and stat["flagged"] == 3


async def test_the_dashboard_can_be_scoped_to_a_project(
    client, admin_headers, project, clock
):
    await finish_run(client, admin_headers, project, clock)
    other = (
        await client.post(P, json={"name": "Empty"}, headers=admin_headers)
    ).json()["id"]
    assert (await dashboard(client, admin_headers, f"?project_id={project}"))[
        "total_runs"
    ] == 1
    scoped = await dashboard(client, admin_headers, f"?project_id={other}")
    assert scoped["total_runs"] == 0 and scoped["total_detections"] == 0
    assert scoped["project_id"] == other


async def test_someone_else_cannot_read_another_users_dashboard(
    client, admin_headers, project, clock, login_as
):
    await finish_run(client, admin_headers, project, clock)  # the service account's run
    login_as("mallory", UserRole.USER)
    # Asking for the service account's activity changes nothing: own data only.
    data = await dashboard(client, {}, "?user_id=service")
    assert data["user_id"] == "mallory"
    assert data["total_tasks"] == 0 and data["by_service"] == []
    login_as("root", UserRole.ADMIN)
    assert (await dashboard(client, {}, "?user_id=service"))["total_runs"] == 1
