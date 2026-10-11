import io
import uuid

import pytest

from app.models.enums import UserRole

P = "/api/v1/projects"
SERVICES = {
    "liteparse-ocr": "liteparse-ocr",
    "ner": "ner",
    "relation": "relation",
    "classification": "classification",
    "safety": "safety",
}


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
    """The workers have registered themselves."""
    for name, queue in SERVICES.items():
        resp = await client.post(
            "/api/v1/services",
            json={"name": name, "queue": queue, "type": "analyser"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


@pytest.fixture
async def project(client, admin_headers, registered):
    """A project that looks for everything."""
    pid = (await client.post(P, json={"name": "Docs"}, headers=admin_headers)).json()[
        "id"
    ]

    async def add(kind, payload):
        resp = await client.post(
            f"{P}/{pid}/{kind}", json=payload, headers=admin_headers
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


async def run(client, headers, project, **body):
    return await client.post(f"{P}/{project['id']}/runs", json=body, headers=headers)


def by_service(sent):
    return {call[0]: call for call in sent}


# -- text ----------------------------------------------------------------------------
async def test_a_text_goes_to_every_worker_as_pages(
    client, admin_headers, project, sent
):
    resp = await run(client, admin_headers, project, text="Pay FR76 to Tim Cook.")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert [s["step"] for s in body["steps"]] == [
        "ner",
        "relation",
        "classification",
        "safety",
    ]
    assert all(s["waiting"] is False for s in body["steps"])

    calls = by_service(sent)
    assert set(calls) == {"ner", "relation", "classification", "safety"}  # no parser
    pages = [{"page_number": 1, "content": "Pay FR76 to Tim Cook."}]
    for _, _, payload, _ in sent:
        assert payload["pages"] == pages
        assert "awaiting" not in payload
    # Each worker is routed to its own queue, with its task id.
    assert [(c[0], c[3]) for c in sent] == [
        (n, n) for n in ("ner", "relation", "classification", "safety")
    ]
    step_ids = {s["task_id"] for s in body["steps"]}
    assert {c[1] for c in sent} == step_ids


async def test_each_worker_gets_what_the_project_defines(
    client, admin_headers, project, sent
):
    await run(client, admin_headers, project, text="x")
    calls = by_service(sent)

    (entity,) = calls["ner"][2]["entities"]  # the disabled one is not sent
    assert entity == {
        "label": "iban",
        "description": "A bank account",
        "category": "PII",
        "severity": "high",
        "action": "block",
        "threshold": 0.8,
        "enabled": True,
    }
    assert calls["relation"][2]["relations"] == [
        {
            "name": "works_for",
            "description": "person -> organization",
            "threshold": None,
        }
    ]
    (cls,) = calls["classification"][2]["classifications"]
    assert cls["name"] == "doc_type" and cls["multi_label"] is False
    assert cls["labels"] == [
        {"name": "invoice", "description": "A bill"},
        {"name": "other", "description": None},
    ]
    safety = calls["safety"][2]
    assert safety["pii_labels"] == []  # PII is the ner step's job
    (check,) = safety["safety_tasks"]
    assert check["ok_labels"] == ["benign"] and check["multi_label"] is True
    assert check["threshold"] == 0.4


async def test_a_form_feed_starts_a_new_page(client, admin_headers, project, sent):
    await run(client, admin_headers, project, text="first page\fsecond page\f \f")
    pages = by_service(sent)["ner"][2]["pages"]
    assert pages == [
        {"page_number": 1, "content": "first page"},
        {"page_number": 2, "content": "second page"},
    ]


async def test_the_run_is_a_parent_task_of_the_project(
    client, admin_headers, project, sent
):
    run_id = (await run(client, admin_headers, project, text="x")).json()["id"]
    parent = (await client.get(f"/api/v1/tasks/{run_id}", headers=admin_headers)).json()
    assert parent["project_id"] == project["id"] and parent["service_id"] is None
    assert parent["user_id"] == "service"
    kids = (
        await client.get(f"/api/v1/tasks/{run_id}/children", headers=admin_headers)
    ).json()
    assert len(kids) == 4 and all(k["project_id"] == project["id"] for k in kids)
    roots = (
        await client.get(
            f"/api/v1/tasks?project_id={project['id']}&roots_only=true",
            headers=admin_headers,
        )
    ).json()
    assert [t["id"] for t in roots["items"]] == [run_id]


# -- what is applied --------------------------------------------------------------------
async def test_a_kind_can_be_skipped_with_an_empty_list(
    client, admin_headers, project, sent
):
    resp = await run(
        client,
        admin_headers,
        project,
        text="x",
        relation_ids=[],
        classification_ids=[],
        safety_ids=[],
    )
    assert [s["step"] for s in resp.json()["steps"]] == ["ner"]
    assert [c[0] for c in sent] == ["ner"]


async def test_chosen_ids_are_applied_even_if_disabled(
    client, admin_headers, project, sent
):
    await run(
        client,
        admin_headers,
        project,
        text="x",
        entity_ids=[project["old"]["id"]],
        relation_ids=[],
        classification_ids=[],
        safety_ids=[],
    )
    (entity,) = by_service(sent)["ner"][2]["entities"]
    assert entity["label"] == "legacy" and entity["enabled"] is False


async def test_a_definition_of_another_project_is_refused(
    client, admin_headers, project, sent
):
    other = (
        await client.post(P, json={"name": "Other"}, headers=admin_headers)
    ).json()["id"]
    foreign = (
        await client.post(
            f"{P}/{other}/entities", json={"label": "x"}, headers=admin_headers
        )
    ).json()["id"]
    resp = await run(client, admin_headers, project, text="x", entity_ids=[foreign])
    assert resp.status_code == 404
    assert sent == []


async def test_nothing_to_apply_is_refused(client, admin_headers, registered, sent):
    empty = (
        await client.post(P, json={"name": "Empty"}, headers=admin_headers)
    ).json()["id"]
    resp = await client.post(
        f"{P}/{empty}/runs", json={"text": "x"}, headers=admin_headers
    )
    assert resp.status_code == 409 and "Nothing to apply" in resp.json()["detail"]
    assert sent == []


async def test_a_missing_worker_refuses_the_whole_run(
    client, admin_headers, project, sent
):
    services = (await client.get("/api/v1/services", headers=admin_headers)).json()[
        "items"
    ]
    relation = next(s for s in services if s["name"] == "relation")
    await client.delete(f"/api/v1/services/{relation['id']}", headers=admin_headers)
    resp = await run(client, admin_headers, project, text="x")
    assert resp.status_code == 409 and "relation" in resp.json()["detail"]
    assert sent == []
    # Nothing was created: a run starts whole or not at all.
    assert (await client.get("/api/v1/tasks", headers=admin_headers)).json()[
        "total"
    ] == 0


@pytest.mark.parametrize(
    "body",
    [{}, {"text": "  "}, {"text": "x", "file_ids": [str(uuid.uuid4())]}],
)
async def test_one_source_is_required(client, admin_headers, project, sent, body):
    assert (await run(client, admin_headers, project, **body)).status_code == 422


async def test_another_users_project_is_not_runnable(
    client, admin_headers, project, sent, login_as
):
    login_as("mallory", UserRole.USER)
    resp = await client.post(f"{P}/{project['id']}/runs", json={"text": "x"})
    assert resp.status_code == 404 and sent == []


# -- files -------------------------------------------------------------------------------
async def upload(client, headers, name="a.pdf"):
    resp = await client.post(
        "/api/v1/files",
        files={"file": (name, io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_files_go_to_the_parser_first_and_the_rest_waits(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    resp = await run(
        client, admin_headers, project, file_ids=[file["id"]], blur_screenshots=False
    )
    assert resp.status_code == 201, resp.text
    steps = resp.json()["steps"]
    assert [(s["step"], s["waiting"]) for s in steps] == [
        ("parser", False),
        ("ner", True),
        ("relation", True),
        ("classification", True),
        ("safety", True),
    ]
    # Only the parser is sent, with the file by its key in the bucket.
    assert [c[0] for c in sent] == ["liteparse-ocr"]
    assert sent[0][2] == {
        "files": [
            {"s3_key": file["s3_key"], "filename": "a.pdf", "mime": "application/pdf"}
        ],
        "blur_screenshots": False,
    }
    # The file now belongs to the project.
    meta = (
        await client.get(f"/api/v1/files/{file['id']}", headers=admin_headers)
    ).json()
    assert meta["project_id"] == project["id"]


async def test_the_parser_output_releases_the_waiting_workers(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    steps = (await run(client, admin_headers, project, file_ids=[file["id"]])).json()[
        "steps"
    ]
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

    calls = by_service(sent)
    assert set(calls) == {"ner", "relation", "classification", "safety"}
    for _, _, payload, _ in sent:
        assert payload["pages"] == pages  # the parser's pages, boxes included
        assert "awaiting" not in payload
    assert calls["ner"][2]["entities"][0]["label"] == "iban"  # the project's data kept

    # Released once: a second parser update does not send them again.
    sent.clear()
    await client.patch(
        f"/api/v1/tasks/{parser_id}", json={"progress": 100}, headers=admin_headers
    )
    assert sent == []


@pytest.mark.parametrize(
    "final", [{"status": "error", "error": "bad pdf"}, {"status": "revoked"}]
)
async def test_a_failed_parser_fails_the_rest_of_the_run(
    client, admin_headers, project, sent, final
):
    file = await upload(client, admin_headers)
    resp = await run(client, admin_headers, project, file_ids=[file["id"]])
    run_id, parser_id = resp.json()["id"], resp.json()["steps"][0]["task_id"]
    sent.clear()

    await client.patch(f"/api/v1/tasks/{parser_id}", json=final, headers=admin_headers)
    assert sent == []  # nothing is sent to the analysis workers
    kids = (
        await client.get(f"/api/v1/tasks/{run_id}/children", headers=admin_headers)
    ).json()
    waiting = [k for k in kids if k["id"] != parser_id]
    assert len(waiting) == 4
    assert all(k["status"] == "error" and "parser" in k["error"] for k in waiting)
    parent = (await client.get(f"/api/v1/tasks/{run_id}", headers=admin_headers)).json()
    assert parent["status"] == "error"


async def test_a_parser_without_pages_fails_the_rest(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    resp = await run(client, admin_headers, project, file_ids=[file["id"]])
    parser_id = resp.json()["steps"][0]["task_id"]
    sent.clear()
    await client.patch(
        f"/api/v1/tasks/{parser_id}",
        json={"status": "success", "output_data": {"pages": []}},
        headers=admin_headers,
    )
    assert sent == []
    kids = (
        await client.get(
            f"/api/v1/tasks/{resp.json()['id']}/children", headers=admin_headers
        )
    ).json()
    assert {k["status"] for k in kids if k["id"] != parser_id} == {"error"}


async def test_the_run_succeeds_when_every_worker_does(
    client, admin_headers, project, sent
):
    run_id = (await run(client, admin_headers, project, text="x")).json()["id"]
    kids = (
        await client.get(f"/api/v1/tasks/{run_id}/children", headers=admin_headers)
    ).json()
    for kid in kids:
        await client.patch(
            f"/api/v1/tasks/{kid['id']}",
            json={"status": "success", "progress": 100, "output_data": {}},
            headers=admin_headers,
        )
    parent = (await client.get(f"/api/v1/tasks/{run_id}", headers=admin_headers)).json()
    assert (parent["status"], parent["progress"]) == ("success", 100)


async def test_someone_elses_file_is_refused(
    client, admin_headers, project, sent, login_as
):
    file = await upload(client, admin_headers)  # owned by the service account
    login_as("mallory", UserRole.USER)
    pid = (await client.post(P, json={"name": "Mine"})).json()["id"]
    await client.post(f"{P}/{pid}/entities", json={"label": "x"})
    resp = await client.post(f"{P}/{pid}/runs", json={"file_ids": [file["id"]]})
    assert resp.status_code == 404 and sent == []
