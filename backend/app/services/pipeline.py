"""How a finished task feeds the tasks of its run that wait for it.

A task created with ``awaiting`` (the id of the task it waits for) and ``feed``
(what to build from it) in its input is released by ``TaskService`` when that
task ends: ``feed`` turns the finished task into the waiter's real input.

* ``pages``: the parser's pages (text, boxes, screenshot key) for the analysis
  workers (ner, relation, classification, safety).
* ``images``: only the screenshot key of each parsed page, for the image
  classification worker (no text: nothing readable is copied to its row).
* ``anonymize``: the pages and the flagged entities found by the ner task, for
  the anonymize worker.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import TaskStatus
from app.models.task import Task

CONTROL_KEYS = ("awaiting", "feed")


class CannotFeed(Exception):
    """The waiting task cannot be built: it fails with this reason."""


def anonymize_input(ner_task: Task) -> dict[str, Any]:
    """What the anonymize worker gets: pages, the spans to hide, their boxes."""
    pages = [
        {
            "page_number": page.get("page_number"),
            "content": page.get("content", ""),
            "s3_key": page.get("s3_key"),
        }
        for page in ner_task.input_data.get("pages") or []
    ]
    anonymized = []
    for page in (ner_task.output_data or {}).get("pages") or []:
        # Entities whose action is "allow" are reported, not hidden.
        entities = [e for e in page.get("entities") or [] if e.get("flagged")]
        if page.get("page_number") is None or not entities:
            continue
        anonymized.append(
            {
                "page_number": page["page_number"],
                "span": [
                    {
                        "start": e["start"],
                        "end": e["end"],
                        "text": e["text"],
                        "label": e["label"],
                    }
                    for e in entities
                ],
                "bboxes": [
                    {**box, "text": e["text"], "label": e["label"]}
                    for e in entities
                    for box in e.get("bboxes") or []
                ],
            }
        )
    # blurred: every character becomes "*", spans a visible [LABEL] marker, and
    # the page images are replaced by a blurred copy with the labelled boxes.
    return {"pages": pages, "anonymized_pages": anonymized, "blurred": True}


def feed(
    waiter_input: dict[str, Any],
    finished: Task,
    output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The waiter's input, built from ``finished``. Raises ``CannotFeed``.

    ``output`` is the task's output as the worker sent it, when the stored one
    has been masked (private runs): the workers still get the real pages.
    """
    if output is None:
        output = finished.output_data
    kind = waiter_input.get("feed", "pages")
    payload = {k: v for k, v in waiter_input.items() if k not in CONTROL_KEYS}
    if kind == "pages":
        if finished.status != TaskStatus.SUCCESS:
            raise CannotFeed(
                f"The parser did not finish ({finished.status.value}): "
                f"{finished.error or 'no details'}"
            )
        pages = (output or {}).get("pages")
        if not pages:
            raise CannotFeed("The parser found no page.")
        payload["pages"] = pages
    elif kind == "images":
        if finished.status != TaskStatus.SUCCESS:
            raise CannotFeed(
                f"The parser did not finish ({finished.status.value}): "
                f"{finished.error or 'no details'}"
            )
        screenshots = [
            {"page_number": page.get("page_number"), "s3_key": page["s3_key"]}
            for page in (output or {}).get("pages") or []
            if page.get("s3_key")
        ]
        if not screenshots:
            raise CannotFeed("The parser produced no page screenshot to classify.")
        payload["pages"] = screenshots
    elif kind == "anonymize":
        if finished.status != TaskStatus.SUCCESS:
            raise CannotFeed(
                f"The entity extraction did not finish ({finished.status.value}): "
                f"{finished.error or 'no details'}"
            )
        payload.update(anonymize_input(finished))
    else:
        raise CannotFeed(f"Unknown feed '{kind}'.")
    return payload
