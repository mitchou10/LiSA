import pytest
from httpx import AsyncClient

from app.models.enums import UserRole

P = "/api/v1/projects"


async def _project(client, headers, name="Contracts", **extra):
    resp = await client.post(P, json={"name": name, **extra}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_project_crud(client: AsyncClient, admin_headers):
    created = await _project(client, admin_headers, description="Legal docs")
    assert created["created_by"] == "service"
    assert created["description"] == "Legal docs"
    pid = created["id"]

    resp = await client.get(f"{P}/{pid}", headers=admin_headers)
    assert resp.json()["name"] == "Contracts"

    resp = await client.patch(
        f"{P}/{pid}", json={"name": " Contracts v2 "}, headers=admin_headers
    )
    assert resp.json()["name"] == "Contracts v2"
    assert resp.json()["description"] == "Legal docs"  # untouched

    assert (await client.delete(f"{P}/{pid}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"{P}/{pid}", headers=admin_headers)).status_code == 404


async def test_requires_authentication(client: AsyncClient):
    assert (await client.get(P)).status_code == 401
    assert (await client.post(P, json={"name": "x"})).status_code == 401


async def test_project_name_is_unique_per_owner(client, admin_headers, login_as):
    await _project(client, admin_headers, "Same")
    resp = await client.post(P, json={"name": "same"}, headers=admin_headers)
    assert resp.status_code == 409  # case-insensitive
    # Another user can use the same name.
    login_as("bob", UserRole.USER)
    resp = await client.post(P, json={"name": "Same"})
    assert resp.status_code == 201
    assert resp.json()["created_by"] == "bob"


async def test_projects_are_private_to_their_owner_but_not_to_admins(
    client, admin_headers, login_as
):
    login_as("bob", UserRole.USER)
    bob_project = (await client.post(P, json={"name": "Bob's"})).json()

    login_as("alice", UserRole.USER)
    assert (await client.get(f"{P}/{bob_project['id']}")).status_code == 404
    assert (
        await client.patch(f"{P}/{bob_project['id']}", json={"name": "x"})
    ).status_code == 404
    assert (await client.delete(f"{P}/{bob_project['id']}")).status_code == 404
    assert (await client.get(P)).json()["total"] == 0
    resp = await client.get(f"{P}/{bob_project['id']}/entities")
    assert resp.status_code == 404  # the catalog follows the project

    # An admin sees everything.
    login_as("root", UserRole.ADMIN)
    assert (await client.get(f"{P}/{bob_project['id']}")).status_code == 200
    assert (await client.get(P)).json()["total"] == 1


async def test_list_shows_counts(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    # Labels that are not among the seeded PII entities.
    await client.post(
        f"{P}/{pid}/entities", json={"label": "account"}, headers=admin_headers
    )
    await client.post(
        f"{P}/{pid}/entities", json={"label": "customer"}, headers=admin_headers
    )
    await client.post(
        f"{P}/{pid}/relations", json={"name": "works_for"}, headers=admin_headers
    )
    await client.post(
        f"{P}/{pid}/classifications",
        json={"name": "type", "labels": ["a", "b"]},
        headers=admin_headers,
    )
    (item,) = (await client.get(P, headers=admin_headers)).json()["items"]
    # New projects are seeded with the default PII entities and safety checks.
    assert (item["entities"], item["relations"], item["classifications"]) == (
        12,
        1,
        1,
    )
    assert item["safety_checks"] == 3


# -- entities ---------------------------------------------------------------------
async def test_entity_defaults_and_normalization(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/entities",
        json={
            "label": " account number ",
            "category": "pii",
            "description": "A bank account",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    e = resp.json()
    assert (e["label"], e["category"]) == ("account number", "PII")
    assert (e["severity"], e["action"], e["enabled"]) == ("medium", "redact", True)
    assert e["threshold"] is None and e["created_by"] == "service"


async def test_seeded_definitions_can_be_renamed_and_deleted(client, admin_headers):
    """The seeded rows are plain catalog rows: edit or delete them at will."""
    pid = (await _project(client, admin_headers))["id"]
    seeded = (await client.get(f"{P}/{pid}/entities", headers=admin_headers)).json()
    iban = next(e for e in seeded if e["label"] == "iban")
    # A seeded label can be renamed, then recreated under its old name.
    resp = await client.patch(
        f"{P}/{pid}/entities/{iban['id']}",
        json={"label": "bank account"},
        headers=admin_headers,
    )
    assert resp.status_code == 200 and resp.json()["label"] == "bank account"
    resp = await client.post(
        f"{P}/{pid}/entities", json={"label": "iban"}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    # And deleted like any other row.
    assert (
        await client.delete(
            f"{P}/{pid}/entities/{resp.json()['id']}", headers=admin_headers
        )
    ).status_code == 204


async def test_entity_update_and_delete(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    eid = (
        await client.post(
            f"{P}/{pid}/entities", json={"label": "account"}, headers=admin_headers
        )
    ).json()["id"]
    resp = await client.patch(
        f"{P}/{pid}/entities/{eid}",
        json={
            "severity": "high",
            "action": "block",
            "threshold": 0.8,
            "enabled": False,
        },
        headers=admin_headers,
    )
    e = resp.json()
    assert (e["severity"], e["action"], e["threshold"], e["enabled"]) == (
        "high",
        "block",
        0.8,
        False,
    )
    assert e["label"] == "account"
    assert (
        await client.delete(f"{P}/{pid}/entities/{eid}", headers=admin_headers)
    ).status_code == 204
    assert (
        await client.get(f"{P}/{pid}/entities/{eid}", headers=admin_headers)
    ).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"label": ""},
        {"label": "x", "threshold": 3},
        {"label": "x", "severity": "huge"},
        {"label": "x", "action": "explode"},
    ],
)
async def test_entity_validation(client, admin_headers, payload):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(f"{P}/{pid}/entities", json=payload, headers=admin_headers)
    assert resp.status_code == 422


async def test_names_are_unique_in_a_project_not_across(client, admin_headers):
    p1 = (await _project(client, admin_headers, "One"))["id"]
    p2 = (await _project(client, admin_headers, "Two"))["id"]
    assert (
        await client.post(
            f"{P}/{p1}/entities", json={"label": "account"}, headers=admin_headers
        )
    ).status_code == 201
    dup = await client.post(
        f"{P}/{p1}/entities", json={"label": "ACCOUNT"}, headers=admin_headers
    )
    assert dup.status_code == 409
    assert (
        await client.post(
            f"{P}/{p2}/entities", json={"label": "account"}, headers=admin_headers
        )
    ).status_code == 201


async def test_definitions_do_not_leak_between_projects(client, admin_headers):
    p1 = (await _project(client, admin_headers, "One"))["id"]
    p2 = (await _project(client, admin_headers, "Two"))["id"]
    eid = (
        await client.post(
            f"{P}/{p1}/entities", json={"label": "account"}, headers=admin_headers
        )
    ).json()["id"]
    assert (
        await client.get(f"{P}/{p2}/entities/{eid}", headers=admin_headers)
    ).status_code == 404
    # The fresh project only holds its seeded PII entities.
    labels = {
        e["label"]
        for e in (await client.get(f"{P}/{p2}/entities", headers=admin_headers)).json()
    }
    assert "account" not in labels and "person" in labels


async def test_deleting_a_project_deletes_what_it_looks_for(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    await client.post(f"{P}/{pid}/relations", json={"name": "r"}, headers=admin_headers)
    await client.post(
        f"{P}/{pid}/classifications",
        json={"name": "c", "labels": ["a"]},
        headers=admin_headers,
    )
    assert (await client.delete(f"{P}/{pid}", headers=admin_headers)).status_code == 204
    again = (await _project(client, admin_headers))["id"]
    assert (
        await client.get(f"{P}/{again}/relations", headers=admin_headers)
    ).json() == []


# -- relations ---------------------------------------------------------------------
async def test_relation_crud(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/relations",
        json={"name": "works_for", "description": "person -> organization"},
        headers=admin_headers,
    )
    rid = resp.json()["id"]
    assert resp.json()["enabled"] is True
    resp = await client.patch(
        f"{P}/{pid}/relations/{rid}", json={"threshold": 0.7}, headers=admin_headers
    )
    assert resp.json()["threshold"] == 0.7
    assert (await client.get(f"{P}/{pid}/relations", headers=admin_headers)).json()[0][
        "id"
    ] == rid


# -- classifications ------------------------------------------------------------------
async def test_classification_with_labels_in_order(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/classifications",
        json={
            "name": "doc_type",
            "multi_label": False,
            "labels": [
                {"name": "invoice", "description": "A bill"},
                "contract",
                {"name": "other"},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    c = resp.json()
    assert [(lb["name"], lb["position"]) for lb in c["labels"]] == [
        ("invoice", 0),
        ("contract", 1),
        ("other", 2),
    ]
    assert c["labels"][0]["description"] == "A bill" and c["multi_label"] is False


async def test_classification_update_replaces_labels(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    cid = (
        await client.post(
            f"{P}/{pid}/classifications",
            json={"name": "t", "labels": ["a", "b"]},
            headers=admin_headers,
        )
    ).json()["id"]
    resp = await client.patch(
        f"{P}/{pid}/classifications/{cid}",
        json={"multi_label": True, "threshold": 0.5, "labels": ["x", "y", "z"]},
        headers=admin_headers,
    )
    c = resp.json()
    assert c["multi_label"] is True and c["threshold"] == 0.5
    assert [lb["name"] for lb in c["labels"]] == ["x", "y", "z"]
    # Without labels in the payload they are kept.
    resp = await client.patch(
        f"{P}/{pid}/classifications/{cid}",
        json={"enabled": False},
        headers=admin_headers,
    )
    assert [lb["name"] for lb in resp.json()["labels"]] == ["x", "y", "z"]


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "t", "labels": []},
        {"name": "t"},
        {"name": "t", "labels": ["a", "A"]},
        {"name": "t", "labels": [{"description": "no name"}]},
    ],
)
async def test_classification_validation(client, admin_headers, payload):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/classifications", json=payload, headers=admin_headers
    )
    assert resp.status_code == 422


# -- safety ------------------------------------------------------------------------------
async def test_safety_check_with_ok_labels(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/safety",
        json={
            "name": "jailbreak",
            "multi_label": True,
            "threshold": 0.4,
            "labels": [
                {"name": "prompt_injection"},
                {"name": "benign", "is_ok": True},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    labels = resp.json()["labels"]
    assert [(lb["name"], lb["is_ok"]) for lb in labels] == [
        ("prompt_injection", False),
        ("benign", True),
    ]


async def test_safety_needs_an_ok_label(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/safety",
        json={"name": "s", "labels": ["bad", "worse"]},
        headers=admin_headers,
    )
    assert resp.status_code == 422
    ok = await client.post(
        f"{P}/{pid}/safety",
        json={"name": "s", "labels": [{"name": "safe", "is_ok": True}, "bad"]},
        headers=admin_headers,
    )
    sid = ok.json()["id"]
    resp = await client.patch(
        f"{P}/{pid}/safety/{sid}", json={"labels": ["bad"]}, headers=admin_headers
    )
    assert resp.status_code == 422


async def test_classification_labels_have_no_ok_flag_effect(client, admin_headers):
    pid = (await _project(client, admin_headers))["id"]
    resp = await client.post(
        f"{P}/{pid}/classifications",
        json={"name": "t", "labels": [{"name": "a", "is_ok": True}]},
        headers=admin_headers,
    )
    assert resp.status_code == 201  # accepted, but a classification has no "ok" notion
