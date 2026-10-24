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
    "anonymize-v2": "anonymize-v2",
    "image-classification": "image-classification",
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
    # The seeded definitions are disabled first: an empty project refuses.
    for kind in ("entities", "safety"):
        for row in (
            await client.get(f"{P}/{empty}/{kind}", headers=admin_headers)
        ).json():
            resp = await client.patch(
                f"{P}/{empty}/{kind}/{row['id']}",
                json={"enabled": False},
                headers=admin_headers,
            )
            assert resp.status_code == 200, resp.text
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
        ("image_classification", True),
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
    assert set(calls) == {
        "ner",
        "relation",
        "classification",
        "image-classification",
        "safety",
    }
    shots = [{"page_number": 1, "s3_key": "pages/t/1/1.png"}]
    for name, _, payload, _ in sent:
        # The text workers get the parser's pages, boxes included; the image
        # model only the screenshot keys.
        assert payload["pages"] == (shots if name == "image-classification" else pages)
        assert "awaiting" not in payload and "feed" not in payload
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
    assert len(waiting) == 5
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


# -- anonymize (hide what was found, on request) --------------------------------------
def _ner_output(entities_by_page):
    return {
        "pages": [
            {"page_number": n, "entities": entities}
            for n, entities in entities_by_page.items()
        ]
    }


def _entity(label, text, start, flagged=True, bboxes=()):
    return {
        "id": "e0",
        "label": label,
        "text": text,
        "start": start,
        "end": start + len(text),
        "flagged": flagged,
        "bboxes": list(bboxes),
    }


async def _finish(client, headers, task_id, output, status="success"):
    resp = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": status, "progress": 100, "output_data": output},
        headers=headers,
    )
    assert resp.status_code == 200


async def test_anonymize_waits_for_the_entities_then_hides_them(
    client, admin_headers, project, sent
):
    resp = await run(
        client,
        admin_headers,
        project,
        text="Maria Garcia lives in Paris",
        anonymize=True,
    )
    assert resp.status_code == 201, resp.text
    steps = resp.json()["steps"]
    assert [s["step"] for s in steps][-1] == "anonymize"
    assert steps[-1]["waiting"] is True
    assert resp.json()["steps"][-1]["service"] == "anonymize-v2"
    # The analysis workers start now; the anonymizer does not.
    assert "anonymize-v2" not in {c[0] for c in sent}

    ner_id = next(s["task_id"] for s in steps if s["step"] == "ner")
    sent.clear()
    box = {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}
    await _finish(
        client,
        admin_headers,
        ner_id,
        _ner_output(
            {
                1: [
                    _entity("person", "Maria Garcia", 0, bboxes=[box]),
                    _entity(
                        "city", "Paris", 22, flagged=False
                    ),  # "allow": reported, not hidden
                ]
            }
        ),
    )
    (call,) = [c for c in sent if c[0] == "anonymize-v2"]
    payload = call[2]
    assert "awaiting" not in payload and "feed" not in payload
    assert payload["blurred"] is True
    # Anonymize is private: the text in the database is masked, and it is what
    # this worker gets (blurred, every character is "*" anyway).
    assert payload["pages"] == [
        {"page_number": 1, "content": "***** ****** ***** ** *****", "s3_key": None}
    ]
    (page,) = payload["anonymized_pages"]
    assert page["page_number"] == 1
    # Offsets and labels are what the worker needs; the entity text is masked.
    assert page["span"] == [
        {"start": 0, "end": 12, "text": "***** ******", "label": "person"}
    ]
    assert page["bboxes"] == [{**box, "text": "***** ******", "label": "person"}]


async def test_a_page_without_flagged_entity_is_left_alone(
    client, admin_headers, project, sent
):
    resp = await run(client, admin_headers, project, text="one\ftwo", anonymize=True)
    ner_id = next(s["task_id"] for s in resp.json()["steps"] if s["step"] == "ner")
    sent.clear()
    await _finish(
        client,
        admin_headers,
        ner_id,
        _ner_output({1: [], 2: [_entity("iban", "FR76", 0)]}),
    )
    payload = next(c[2] for c in sent if c[0] == "anonymize-v2")
    assert [p["page_number"] for p in payload["anonymized_pages"]] == [2]
    assert len(payload["pages"]) == 2  # every page is returned, hidden or not


async def test_anonymize_of_a_file_carries_the_screenshot_keys(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    steps = (
        await run(client, admin_headers, project, file_ids=[file["id"]], anonymize=True)
    ).json()["steps"]
    by_step = {s["step"]: s["task_id"] for s in steps}
    pages = [{"page_number": 1, "content": "Pay FR76", "s3_key": "pages/t/1/1.png"}]
    await _finish(client, admin_headers, by_step["parser"], {"pages": pages})
    await _finish(
        client,
        admin_headers,
        by_step["ner"],
        _ner_output({1: [_entity("iban", "FR76", 4)]}),
    )
    payload = next(c[2] for c in sent if c[0] == "anonymize-v2")
    assert payload["pages"] == [
        {"page_number": 1, "content": "*** ****", "s3_key": "pages/t/1/1.png"}
    ]
    assert payload["anonymized_pages"][0]["span"][0]["label"] == "iban"


async def test_anonymize_fails_when_the_entities_do(
    client, admin_headers, project, sent
):
    resp = await run(client, admin_headers, project, text="x", anonymize=True)
    body = resp.json()
    ner_id = next(s["task_id"] for s in body["steps"] if s["step"] == "ner")
    sent.clear()
    await client.patch(
        f"/api/v1/tasks/{ner_id}",
        json={"status": "error", "error": "model down"},
        headers=admin_headers,
    )
    assert "anonymize-v2" not in {c[0] for c in sent}
    kids = (
        await client.get(f"/api/v1/tasks/{body['id']}/children", headers=admin_headers)
    ).json()
    anonymize = next(k for k in kids if k["id"] == body["steps"][-1]["task_id"])
    assert anonymize["status"] == "error" and "entity extraction" in anonymize["error"]


async def test_anonymize_needs_entities(client, admin_headers, project, sent):
    resp = await run(
        client, admin_headers, project, text="x", entity_ids=[], anonymize=True
    )
    assert resp.status_code == 409 and "entit" in resp.json()["detail"]
    assert sent == []


async def test_anonymize_needs_its_worker(client, admin_headers, project, sent):
    services = (await client.get("/api/v1/services", headers=admin_headers)).json()[
        "items"
    ]
    anonymizer = next(s for s in services if s["name"] == "anonymize-v2")
    await client.delete(f"/api/v1/services/{anonymizer['id']}", headers=admin_headers)
    resp = await run(client, admin_headers, project, text="x", anonymize=True)
    assert resp.status_code == 409 and "anonymize-v2" in resp.json()["detail"]
    assert sent == []
    # Without it requested, the run does not need that worker.
    assert (await run(client, admin_headers, project, text="x")).status_code == 201


async def test_a_run_does_not_anonymize_unless_asked(
    client, admin_headers, project, sent
):
    steps = (await run(client, admin_headers, project, text="x")).json()["steps"]
    assert "anonymize" not in [s["step"] for s in steps]


# -- private runs: nothing readable in the database -------------------------------------
from app.services.privacy import mask, mask_text_fields


def test_mask_keeps_length_and_layout():
    assert mask("Maria Garcia\nParis 75") == "***** ******\n***** **"
    assert mask("") == ""


def test_mask_text_fields_only_touches_what_documents_say():
    data = {
        "pages": [
            {
                "page_number": 1,
                "content": "Pay FR76",
                "s3_key": "pages/t/1/1.png",
                "words": [{"text": "Pay", "x": 0.1, "start": 0, "end": 3}],
            }
        ],
        "entities": [
            {"label": "iban", "text": "FR76", "score": 0.9, "bboxes": [{"x": 0.2}]}
        ],
        "labels": ["invoice"],
    }
    out = mask_text_fields(data)
    assert out["pages"][0]["content"] == "*** ****"
    assert out["pages"][0]["words"] == [{"text": "***", "x": 0.1, "start": 0, "end": 3}]
    assert out["pages"][0]["s3_key"] == "pages/t/1/1.png"
    assert out["entities"] == [
        {"label": "iban", "text": "****", "score": 0.9, "bboxes": [{"x": 0.2}]}
    ]
    assert out["labels"] == ["invoice"]
    assert data["pages"][0]["content"] == "Pay FR76"  # the original is untouched


async def _children(client, headers, run_id):
    resp = await client.get(f"/api/v1/tasks/{run_id}/children", headers=headers)
    return {k["id"]: k for k in resp.json()}


async def test_a_private_text_run_stores_no_readable_text(
    client, admin_headers, project, sent
):
    text = "Maria Garcia lives in Paris"
    resp = await run(client, admin_headers, project, text=text, anonymize=True)
    body = resp.json()
    # The workers got the real text...
    assert all(c[2]["pages"][0]["content"] == text for c in sent)
    # ...the database did not keep it.
    kids = await _children(client, admin_headers, body["id"])
    for kid in kids.values():
        if "pages" in kid["input_data"]:
            assert kid["input_data"]["pages"][0]["content"] == mask(text)
    parent = (
        await client.get(f"/api/v1/tasks/{body['id']}", headers=admin_headers)
    ).json()
    assert text not in str(parent) and parent["input_data"]["anonymize"] is True


async def test_a_private_output_is_stored_masked_but_the_next_worker_gets_it_clear(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    body = (
        await run(client, admin_headers, project, file_ids=[file["id"]], anonymize=True)
    ).json()
    parser_id = next(s["task_id"] for s in body["steps"] if s["step"] == "parser")
    sent.clear()
    pages = [
        {
            "page_number": 1,
            "content": "Maria Garcia pays FR76",
            "s3_key": "pages/t/1/1.png",
            "words": [{"text": "Maria", "x": 0.1, "start": 0, "end": 5}],
        }
    ]
    await _finish(client, admin_headers, parser_id, {"pages": pages})

    # Sent clear to the analysis workers...
    for call in sent:
        if call[0] != "image-classification":  # that one only gets screenshot keys
            assert call[2]["pages"] == pages
    # ...stored masked, for the parser's output and for each waiting task.
    kids = await _children(client, admin_headers, body["id"])
    stored = kids[parser_id]["output_data"]["pages"][0]
    assert stored["content"] == mask("Maria Garcia pays FR76")
    assert stored["words"][0]["text"] == "*****" and stored["words"][0]["x"] == 0.1
    assert stored["s3_key"] == "pages/t/1/1.png"
    for kid in kids.values():
        if kid["id"] != parser_id and "pages" in kid["input_data"]:
            page = kid["input_data"]["pages"][0]
            # The image model's row holds no text at all, only the key.
            assert page.get("content", mask("Maria Garcia pays FR76")) == mask(
                "Maria Garcia pays FR76"
            )
    assert "Maria Garcia" not in str(kids)


async def test_the_anonymizer_needs_no_clear_text(client, admin_headers, project, sent):
    """Blurred, every character is "*": the masked stored text gives the same result."""
    body = (
        await run(
            client,
            admin_headers,
            project,
            text="Maria Garcia lives here",
            anonymize=True,
        )
    ).json()
    ner_id = next(s["task_id"] for s in body["steps"] if s["step"] == "ner")
    sent.clear()
    box = {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}
    await _finish(
        client,
        admin_headers,
        ner_id,
        _ner_output({1: [_entity("person", "Maria Garcia", 0, bboxes=[box])]}),
    )
    payload = next(c[2] for c in sent if c[0] == "anonymize-v2")
    assert payload["pages"][0]["content"] == mask("Maria Garcia lives here")
    kids = await _children(client, admin_headers, body["id"])
    entity = kids[ner_id]["output_data"]["pages"][0]["entities"][0]
    assert (
        entity["text"] == mask("Maria Garcia")
        and entity["start"] == 0
        and entity["bboxes"] == [box]
    )


async def test_a_public_run_stores_what_it_always_did(
    client, admin_headers, project, sent
):
    text = "Maria Garcia lives in Paris"
    body = (await run(client, admin_headers, project, text=text)).json()
    kids = await _children(client, admin_headers, body["id"])
    assert all(k["input_data"]["pages"][0]["content"] == text for k in kids.values())
    ner_id = next(s["task_id"] for s in body["steps"] if s["step"] == "ner")
    await _finish(
        client,
        admin_headers,
        ner_id,
        _ner_output({1: [_entity("person", "Maria Garcia", 0)]}),
    )
    kids = await _children(client, admin_headers, body["id"])
    assert (
        kids[ner_id]["output_data"]["pages"][0]["entities"][0]["text"] == "Maria Garcia"
    )


async def test_a_private_task_cannot_be_retried(client, admin_headers, project, sent):
    body = (
        await run(client, admin_headers, project, text="secret", anonymize=True)
    ).json()
    ner_id = next(s["task_id"] for s in body["steps"] if s["step"] == "ner")
    await client.patch(
        f"/api/v1/tasks/{ner_id}",
        json={"status": "error", "error": "boom"},
        headers=admin_headers,
    )
    sent.clear()
    resp = await client.post(f"/api/v1/tasks/{ner_id}/retry", headers=admin_headers)
    assert resp.status_code == 409 and "private" in resp.json()["detail"]
    assert sent == []  # never re-sent with a masked input


# -- image classification: files are also classified by what they look like ------------
async def test_a_classified_file_also_gets_its_screenshots_classified(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    body = (await run(client, admin_headers, project, file_ids=[file["id"]])).json()
    steps = {s["step"]: s for s in body["steps"]}
    assert steps["image_classification"]["service"] == "image-classification"
    assert steps["image_classification"]["waiting"] is True
    sent.clear()
    pages = [
        {"page_number": 1, "content": "text", "s3_key": "pages/t/1/1.png", "words": []},
        {"page_number": 2, "content": "no screenshot", "s3_key": None},
    ]
    await _finish(client, admin_headers, steps["parser"]["task_id"], {"pages": pages})
    payload = by_service(sent)["image-classification"][2]
    # Only the pages that have a screenshot, as a key: no text.
    assert payload["pages"] == [{"page_number": 1, "s3_key": "pages/t/1/1.png"}]
    # The project's classification, labels with their descriptions.
    (cls,) = payload["classifications"]
    assert cls["name"] == "doc_type" and cls["multi_label"] is False
    assert cls["labels"] == [
        {"name": "invoice", "description": "A bill"},
        {"name": "other", "description": None},
    ]
    assert "awaiting" not in payload and "feed" not in payload


async def test_a_text_run_has_no_image_step(client, admin_headers, project, sent):
    steps = (await run(client, admin_headers, project, text="x")).json()["steps"]
    assert "image_classification" not in [s["step"] for s in steps]
    assert "image-classification" not in {c[0] for c in sent}


async def test_images_are_only_classified_with_classifications(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    steps = (
        await run(
            client, admin_headers, project, file_ids=[file["id"]], classification_ids=[]
        )
    ).json()["steps"]
    assert "image_classification" not in [s["step"] for s in steps]


async def test_the_image_step_can_be_switched_off(client, admin_headers, project, sent):
    file = await upload(client, admin_headers)
    steps = (
        await run(
            client, admin_headers, project, file_ids=[file["id"]], classify_images=False
        )
    ).json()["steps"]
    assert "image_classification" not in [s["step"] for s in steps]
    assert "classification" in [s["step"] for s in steps]


async def test_a_classification_with_one_label_is_left_to_the_text_model(
    client, admin_headers, project, sent
):
    """CLIP compares an image with every label: one label has nothing to be compared with."""
    # Only the one-label classification is applied: no image step is created.
    pid = project["id"]
    one = (
        await client.post(
            f"{P}/{pid}/classifications",
            json={"name": "lonely", "labels": ["only"]},
            headers=admin_headers,
        )
    ).json()
    file = await upload(client, admin_headers)
    steps = (
        await run(
            client,
            admin_headers,
            project,
            file_ids=[file["id"]],
            classification_ids=[one["id"]],
        )
    ).json()["steps"]
    assert "classification" in [s["step"] for s in steps]
    assert "image_classification" not in [s["step"] for s in steps]
    # Alongside a normal one, it is simply not sent to the image model.
    sent.clear()
    body = (
        await run(
            client,
            admin_headers,
            project,
            file_ids=[file["id"]],
            classification_ids=[one["id"], project["doc_type"]["id"]],
        )
    ).json()
    parser_id = next(s["task_id"] for s in body["steps"] if s["step"] == "parser")
    sent.clear()
    await _finish(
        client,
        admin_headers,
        parser_id,
        {"pages": [{"page_number": 1, "content": "x", "s3_key": "pages/t/1/1.png"}]},
    )
    names = [
        c["name"]
        for c in by_service(sent)["image-classification"][2]["classifications"]
    ]
    assert names == ["doc_type"]


async def test_no_screenshot_fails_the_image_step_only(
    client, admin_headers, project, sent
):
    file = await upload(client, admin_headers)
    body = (await run(client, admin_headers, project, file_ids=[file["id"]])).json()
    parser_id = next(s["task_id"] for s in body["steps"] if s["step"] == "parser")
    sent.clear()
    await _finish(
        client,
        admin_headers,
        parser_id,
        {"pages": [{"page_number": 1, "content": "text only", "s3_key": None}]},
    )
    assert {"ner", "relation", "classification", "safety"} <= {c[0] for c in sent}
    assert "image-classification" not in {c[0] for c in sent}
    kids = await _children(client, admin_headers, body["id"])
    image = kids[
        next(s["task_id"] for s in body["steps"] if s["step"] == "image_classification")
    ]
    assert image["status"] == "error" and "screenshot" in image["error"]


async def test_the_image_step_needs_its_worker(client, admin_headers, project, sent):
    services = (await client.get("/api/v1/services", headers=admin_headers)).json()[
        "items"
    ]
    worker = next(s for s in services if s["name"] == "image-classification")
    await client.delete(f"/api/v1/services/{worker['id']}", headers=admin_headers)
    file = await upload(client, admin_headers)
    resp = await run(client, admin_headers, project, file_ids=[file["id"]])
    assert resp.status_code == 409 and "image-classification" in resp.json()["detail"]
    assert sent == []
    # A text run, or a file without the image step, does not need it.
    assert (await run(client, admin_headers, project, text="x")).status_code == 201
    ok = await run(
        client, admin_headers, project, file_ids=[file["id"]], classify_images=False
    )
    assert ok.status_code == 201
