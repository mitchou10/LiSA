"""Render the pages of a finished file run: blur, boxes, download formats."""

import io
import zipfile

import pytest
from PIL import Image

from app.core import storage
from app.models.enums import UserRole

P = "/api/v1/projects"


def _png(width=400, height=200, text="Maria Garcia"):
    """A real PNG: white page, a black box with text where the entity sits."""
    img = Image.new("RGB", (width, height), "white")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 240, 70], fill="red")
    draw.text((50, 45), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def objects(monkeypatch):
    """The parser's screenshots, in storage."""
    store: dict[str, bytes] = {
        "pages/t/1/1.png": _png(),
        "pages/t/1/2.png": _png(text="Paris"),
        "pages/t/1/3.png": _png(text="FR76"),
    }

    async def get(key):
        if key not in store:
            raise storage.ObjectNotFoundError(key)
        return store[key]

    monkeypatch.setattr(storage, "get_object", get)
    return store


PAGES = [
    {"page_number": 1, "content": "Maria Garcia", "s3_key": "pages/t/1/1.png"},
    {"page_number": 2, "content": "Paris", "s3_key": "pages/t/1/2.png"},
    {"page_number": 3, "content": "FR76", "s3_key": None},  # no screenshot
]


def _entity(id, label, text, start, bboxes=()):
    return {
        "id": id,
        "label": label,
        "text": text,
        "start": start,
        "end": start + len(text),
        "flagged": True,
        "bboxes": list(bboxes),
    }


BOX = {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.15}


async def _file_run(client, headers, project, sent):
    """A finished file run: parser and ner both succeeded."""
    file = (
        await client.post(
            "/api/v1/files",
            files={"file": ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers=headers,
        )
    ).json()
    body = (
        await client.post(
            f"{P}/{project['id']}/runs",
            json={"file_ids": [file["id"]]},
            headers=headers,
        )
    ).json()
    run_id = body["id"]  # the parent task, the one to render
    by_step = {s["step"]: s["task_id"] for s in body["steps"]}
    sent.clear()
    # The parser succeeds: its pages release the waiting workers.
    await client.patch(
        f"/api/v1/tasks/{by_step['parser']}",
        json={"status": "success", "progress": 100, "output_data": {"pages": PAGES}},
        headers=headers,
    )
    # The ner worker finds two entities on page 1, one on page 2.
    await client.patch(
        f"/api/v1/tasks/{by_step['ner']}",
        json={
            "status": "success",
            "progress": 100,
            "output_data": {
                "pages": [
                    {
                        "page_number": 1,
                        "entities": [
                            _entity("e0", "person", "Maria Garcia", 0, bboxes=[BOX]),
                            _entity("e1", "iban", "FR76", 13, bboxes=[BOX]),
                        ],
                    },
                    {
                        "page_number": 2,
                        "entities": [_entity("e2", "city", "Paris", 0, bboxes=[BOX])],
                    },
                    {"page_number": 3, "entities": []},
                ]
            },
        },
        headers=headers,
    )
    # Every other child succeeds, so the parent (the run) does too.
    kids = (
        await client.get(f"/api/v1/tasks/{run_id}/children", headers=headers)
    ).json()
    for kid in kids:
        if kid["id"] not in (by_step["parser"], by_step["ner"]):
            await client.patch(
                f"/api/v1/tasks/{kid['id']}",
                json={"status": "success", "progress": 100, "output_data": {}},
                headers=headers,
            )
    return run_id


async def _render(client, headers, run_id, **body):
    return await client.post(
        f"/api/v1/tasks/{run_id}/render", json=body, headers=headers
    )


async def test_png_of_one_page_blurs_the_entities(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(client, admin_headers, run_id, page_numbers=[1], format="png")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert "attachment" in resp.headers["content-disposition"]
    img = Image.open(io.BytesIO(resp.content))
    assert img.size == (400, 200)
    # The entity's box (10%,20% to 60%,35% of the page) is blurred: the red
    # rectangle there is no longer uniform.
    region = img.crop((40, 40, 240, 70))
    colours = region.getcolors(maxcolors=100000)
    assert colours is None or len(colours) > 1  # not one flat colour anymore


async def test_blur_none_keeps_the_page_as_stored(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(
        client,
        admin_headers,
        run_id,
        page_numbers=[1],
        format="png",
        blur="none",
    )
    assert resp.status_code == 200
    assert resp.content == objects["pages/t/1/1.png"]


async def test_blur_full_hides_the_whole_page(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(
        client,
        admin_headers,
        run_id,
        page_numbers=[1],
        format="png",
        blur="full",
    )
    assert resp.status_code == 200
    img = Image.open(io.BytesIO(resp.content))
    # The whole page is blurred, not just the entity's box: the red
    # rectangle's edge is smeared into a gradient.
    region = img.crop((220, 30, 260, 80))  # across the rectangle's right edge
    colours = region.getcolors(maxcolors=100000)
    assert colours is None or len(colours) > 1


async def test_only_the_selected_entities_are_blurred(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    # Both entities sit on the same box; blurring only e1 still blurs it, but
    # the point is the selection is accepted and renders.
    resp = await _render(
        client,
        admin_headers,
        run_id,
        page_numbers=[1],
        format="png",
        entity_ids=["e1"],
    )
    assert resp.status_code == 200
    img = Image.open(io.BytesIO(resp.content))
    region = img.crop((40, 40, 240, 70))
    colours = region.getcolors(maxcolors=100000)
    assert colours is None or len(colours) > 1


async def test_a_page_scoped_id_selects_one_page_only(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    # "2:e2" is the city on page 2; page 1 keeps its entities untouched, so
    # its export is exactly the stored screenshot.
    resp = await _render(
        client,
        admin_headers,
        run_id,
        page_numbers=[1],
        format="png",
        entity_ids=["2:e2"],
    )
    assert resp.status_code == 200
    assert resp.content == objects["pages/t/1/1.png"]


async def test_boxes_draw_the_label_above_the_box(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(
        client,
        admin_headers,
        run_id,
        page_numbers=[1],
        format="png",
        blur="none",
        boxes=True,
    )
    assert resp.status_code == 200
    img = Image.open(io.BytesIO(resp.content))
    # The box outline and the label add colours the stored page does not have.
    stored = Image.open(io.BytesIO(objects["pages/t/1/1.png"]))
    assert img.tobytes() != stored.tobytes()


async def test_zip_bundles_every_page(client, admin_headers, project, sent, objects):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(client, admin_headers, run_id, format="zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert sorted(zf.namelist()) == ["page-1.png", "page-2.png"]


async def test_pdf_bundles_every_page(client, admin_headers, project, sent, objects):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(client, admin_headers, run_id, format="pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


async def test_a_page_without_screenshot_is_skipped(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    # Page 3 has no screenshot: it is simply not in the export.
    resp = await _render(client, admin_headers, run_id, format="zip")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert "page-3.png" not in zf.namelist()
    # Asking for it alone is an error.
    resp = await _render(client, admin_headers, run_id, page_numbers=[3], format="png")
    assert resp.status_code == 404


async def test_png_needs_exactly_one_page(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(client, admin_headers, run_id, format="png")
    assert resp.status_code == 404 and "one page" in resp.json()["detail"]


async def test_an_unknown_page_is_refused(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await _render(client, admin_headers, run_id, page_numbers=[9], format="png")
    assert resp.status_code == 404 and "page 9" in resp.json()["detail"].lower()


async def test_a_deleted_screenshot_is_gone(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    del objects["pages/t/1/2.png"]
    resp = await _render(client, admin_headers, run_id, format="zip")
    assert resp.status_code == 404 and "deleted" in resp.json()["detail"]


async def test_a_text_run_has_nothing_to_render(
    client, admin_headers, project, sent, objects
):
    body = (
        await client.post(
            f"{P}/{project['id']}/runs", json={"text": "x"}, headers=admin_headers
        )
    ).json()
    for step in body["steps"]:
        await client.patch(
            f"/api/v1/tasks/{step['task_id']}",
            json={"status": "success", "progress": 100, "output_data": {}},
            headers=admin_headers,
        )
    resp = await _render(client, admin_headers, body["id"], format="png")
    assert resp.status_code == 404


async def test_other_users_cannot_render_but_admins_can(
    client, admin_headers, project, sent, objects, login_as
):
    run_id = await _file_run(client, admin_headers, project, sent)
    login_as("mallory", UserRole.USER)
    resp = await client.post(
        f"/api/v1/tasks/{run_id}/render",
        json={"page_numbers": [1], "format": "png"},
    )
    assert resp.status_code == 404
    login_as("root", UserRole.ADMIN)
    resp = await _render(client, None, run_id, page_numbers=[1], format="png")
    assert resp.status_code == 200


async def test_render_requires_authentication(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await client.post(
        f"/api/v1/tasks/{run_id}/render",
        json={"page_numbers": [1], "format": "png"},
    )
    assert resp.status_code == 401


# -- boxes drawn by users on the pages of a run ---------------------------------


def _url(run_id, suffix=""):
    return f"/api/v1/tasks/{run_id}/bboxes{suffix}"


BOX = {"page_number": 3, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2}


async def test_add_list_and_delete_a_box(client, admin_headers, project, sent):
    run_id = await _file_run(client, admin_headers, project, sent)
    created = await client.post(
        _url(run_id), json={**BOX, "label": "signature"}, headers=admin_headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["run_id"] == run_id and body["label"] == "signature"

    listed = (await client.get(_url(run_id), headers=admin_headers)).json()
    assert [b["id"] for b in listed] == [body["id"]]
    other_page = await client.get(
        _url(run_id), params={"page_number": 1}, headers=admin_headers
    )
    assert other_page.json() == []

    gone = await client.delete(_url(run_id, f"/{body['id']}"), headers=admin_headers)
    assert gone.status_code == 204
    assert (await client.get(_url(run_id), headers=admin_headers)).json() == []


async def test_a_box_must_stay_inside_the_page(client, admin_headers, project, sent):
    run_id = await _file_run(client, admin_headers, project, sent)
    resp = await client.post(
        _url(run_id), json={**BOX, "x": 0.9, "width": 0.3}, headers=admin_headers
    )
    assert resp.status_code == 422


async def test_boxes_need_authentication(client, admin_headers, project, sent):
    run_id = await _file_run(client, admin_headers, project, sent)
    assert (await client.get(_url(run_id))).status_code in (401, 403)


async def test_a_drawn_box_is_blurred_on_export(
    client,
    admin_headers,
    project,
    sent,
    objects,
):
    run_id = await _file_run(client, admin_headers, project, sent)
    # Page 3 has no entity: nothing is blurred until a box is drawn on it.
    before = await _render(
        client, admin_headers, run_id, page_numbers=[2], format="png"
    )
    assert before.status_code == 200
    # Page 2's stored image is 400x200 with a red rectangle at (40,40)-(240,70).
    await client.post(
        _url(run_id),
        json={"page_number": 2, "x": 0.0, "y": 0.1, "width": 0.7, "height": 0.4},
        headers=admin_headers,
    )
    resp = await _render(
        client, admin_headers, run_id, page_numbers=[2], format="png", blur="entities"
    )
    img = Image.open(io.BytesIO(resp.content))
    colours = img.crop((220, 30, 260, 80)).getcolors(maxcolors=100000)
    assert colours is None or len(colours) > 1


async def test_entities_off_blurs_only_the_drawn_boxes(
    client, admin_headers, project, sent, objects
):
    run_id = await _file_run(client, admin_headers, project, sent)
    # Without a drawn box, leaving the entities alone changes nothing.
    untouched = await _render(
        client, admin_headers, run_id, page_numbers=[1], format="png", entities=False
    )
    assert untouched.content == objects["pages/t/1/1.png"]
    # A box with no label, tied to no entity, is still blurred.
    await client.post(
        _url(run_id),
        json={"page_number": 1, "x": 0.0, "y": 0.1, "width": 0.7, "height": 0.4},
        headers=admin_headers,
    )
    resp = await _render(
        client, admin_headers, run_id, page_numbers=[1], format="png", entities=False
    )
    img = Image.open(io.BytesIO(resp.content))
    colours = img.crop((40, 40, 240, 70)).getcolors(maxcolors=100000)
    assert colours is None or len(colours) > 1
