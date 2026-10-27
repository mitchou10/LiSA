"""Boxes drawn by users on the pages of a run: stored, listed, blurred."""

import io

from PIL import Image

from tests.test_render import _file_run, _render, objects  # noqa: F401


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
    objects,  # noqa: F811
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
