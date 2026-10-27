"""Default runs: analyse without a project, with the seeded defaults.

The same defaults every new project is seeded with (PII entities, safety
checks) are applied: no project to create, nothing to configure. The run is a
parent task like any other, it just belongs to no project.
"""

import io

import pytest

from app.services.project_defaults import default_pii_entities, default_safety_checks

R = "/api/v1/tasks/runs"
SERVICES = ("liteparse-ocr", "ner", "safety", "anonymize-v2")


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
async def registered(client, admin_headers):
    """The workers a default run needs have registered themselves."""
    for name in SERVICES:
        resp = await client.post(
            "/api/v1/services",
            json={"name": name, "queue": name, "type": "analyser"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


def by_service(sent):
    return {call[0]: call for call in sent}


# -- what a default run applies ---------------------------------------------------------
async def test_a_text_is_analysed_with_the_defaults(
    client, admin_headers, registered, sent
):
    resp = await client.post(
        R, json={"text": "Tim Cook pays FR76."}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert [s["step"] for s in body["steps"]] == ["ner", "safety"]
    assert all(s["waiting"] is False for s in body["steps"])
    assert body["project_id"] is None

    calls = by_service(sent)
    assert set(calls) == {"ner", "safety"}  # no parser, no relation, no classification
    pages = [{"page_number": 1, "content": "Tim Cook pays FR76."}]
    for _, _, payload, _ in sent:
        assert payload["pages"] == pages


async def test_the_ner_step_gets_the_default_pii_entities(
    client, admin_headers, registered, sent
):
    await client.post(R, json={"text": "x"}, headers=admin_headers)
    (entity,) = [
        e for e in by_service(sent)["ner"][2]["entities"] if e["label"] == "person"
    ]
    assert entity == {
        "label": "person",
        "description": "A person's full name.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
        "threshold": None,
        "enabled": True,
    }
    # Every seeded entity is applied, nothing more.
    labels = {e["label"] for e in by_service(sent)["ner"][2]["entities"]}
    assert labels == {p["label"] for p in default_pii_entities()}


async def test_the_safety_step_gets_the_default_checks(
    client, admin_headers, registered, sent
):
    await client.post(R, json={"text": "x"}, headers=admin_headers)
    safety = by_service(sent)["safety"][2]
    assert safety["pii_labels"] == []  # PII is the ner step's job
    checks = safety["safety_tasks"]
    assert [c["name"] for c in checks] == [c["name"] for c in default_safety_checks()]
    jailbreak = next(c for c in checks if c["name"] == "jailbreak_detection")
    assert jailbreak["multi_label"] is True
    assert "prompt_injection" in jailbreak["labels"][0]["name"]


async def test_selection_fields_are_ignored(client, admin_headers, registered, sent):
    """A default run applies everything it has: the ids fields change nothing."""
    resp = await client.post(
        R,
        json={"text": "x", "entity_ids": [], "safety_ids": []},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert {c[0] for c in sent} == {"ner", "safety"}


# -- the run is a task like any other ----------------------------------------------------
async def test_the_run_belongs_to_no_project(client, admin_headers, registered, sent):
    run_id = (await client.post(R, json={"text": "x"}, headers=admin_headers)).json()[
        "id"
    ]
    parent = (await client.get(f"/api/v1/tasks/{run_id}", headers=admin_headers)).json()
    assert parent["project_id"] is None
    assert parent["input_data"]["kind"] == "default_run"
    kids = (
        await client.get(f"/api/v1/tasks/{run_id}/children", headers=admin_headers)
    ).json()
    assert len(kids) == 2 and all(k["project_id"] is None for k in kids)
    # No project was created along the way.
    projects = (await client.get("/api/v1/projects", headers=admin_headers)).json()
    assert projects["total"] == 0


async def test_a_missing_worker_refuses_the_whole_run(
    client, admin_headers, registered, sent
):
    services = (await client.get("/api/v1/services", headers=admin_headers)).json()[
        "items"
    ]
    ner = next(s for s in services if s["name"] == "ner")
    await client.delete(f"/api/v1/services/{ner['id']}", headers=admin_headers)
    resp = await client.post(R, json={"text": "x"}, headers=admin_headers)
    assert resp.status_code == 409 and "ner" in resp.json()["detail"]
    assert sent == []
    # Nothing was created: a run starts whole or not at all.
    assert (await client.get("/api/v1/tasks", headers=admin_headers)).json()[
        "total"
    ] == 0


@pytest.mark.parametrize(
    "body", [{}, {"text": "  "}, {"text": "x", "file_ids": [str(io.IOBase())]}]
)
async def test_one_source_is_required(client, admin_headers, registered, body):
    assert (await client.post(R, json=body, headers=admin_headers)).status_code == 422


# -- files ------------------------------------------------------------------------------
async def upload(client, headers, name="a.pdf"):
    resp = await client.post(
        "/api/v1/files",
        files={"file": (name, io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_files_go_to_the_parser_first(client, admin_headers, registered, sent):
    file = await upload(client, admin_headers)
    resp = await client.post(
        R,
        json={"file_ids": [file["id"]], "blur_screenshots": False},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    steps = resp.json()["steps"]
    assert [(s["step"], s["waiting"]) for s in steps] == [
        ("parser", False),
        ("ner", True),
        ("safety", True),
    ]
    assert [c[0] for c in sent] == ["liteparse-ocr"]
    assert sent[0][2]["files"] == [
        {"s3_key": file["s3_key"], "filename": "a.pdf", "mime": "application/pdf"}
    ]
    # The file joins no project.
    meta = (
        await client.get(f"/api/v1/files/{file['id']}", headers=admin_headers)
    ).json()
    assert meta["project_id"] is None


async def test_the_parser_output_releases_the_waiting_workers(
    client, admin_headers, registered, sent
):
    file = await upload(client, admin_headers)
    steps = (
        await client.post(R, json={"file_ids": [file["id"]]}, headers=admin_headers)
    ).json()["steps"]
    parser_id = steps[0]["task_id"]
    sent.clear()

    pages = [
        {
            "page_number": 1,
            "content": "Pay FR76",
            "words": [{"text": "Pay"}],
            "s3_key": "pages/t/1/1.png",
        }
    ]
    resp = await client.patch(
        f"/api/v1/tasks/{parser_id}",
        json={"status": "success", "progress": 100, "output_data": {"pages": pages}},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert {c[0] for c in sent} == {"ner", "safety"}
    for _, _, payload, _ in sent:
        assert payload["pages"] == pages and "awaiting" not in payload


# -- anonymize works too ----------------------------------------------------------------
async def test_anonymize_waits_for_the_entities(
    client, admin_headers, registered, sent
):
    resp = await client.post(
        R,
        json={"text": "Maria Garcia lives in Paris", "anonymize": True},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    steps = resp.json()["steps"]
    assert [s["step"] for s in steps] == ["ner", "safety", "anonymize"]
    assert steps[-1]["waiting"] is True
    assert "anonymize-v2" not in {c[0] for c in sent}

    ner_id = steps[0]["task_id"]
    sent.clear()
    await client.patch(
        f"/api/v1/tasks/{ner_id}",
        json={
            "status": "success",
            "progress": 100,
            "output_data": {
                "pages": [
                    {
                        "page_number": 1,
                        "entities": [
                            {
                                "id": "e0",
                                "label": "person",
                                "text": "Maria Garcia",
                                "start": 0,
                                "end": 12,
                                "flagged": True,
                                "bboxes": [],
                            }
                        ],
                    }
                ]
            },
        },
        headers=admin_headers,
    )
    (call,) = [c for c in sent if c[0] == "anonymize-v2"]
    assert call[2]["anonymized_pages"][0]["span"][0]["label"] == "person"
