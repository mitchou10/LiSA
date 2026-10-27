"""Keep readable text out of the database when a run asks to hide it.

When a run is started with ``anonymize``, the clear text only exists in memory
and in the broker message that carries it to a worker: what is written to the
``tasks`` table has every ``text`` and ``content`` replaced by ``*``. Lengths,
offsets, labels, scores and boxes are untouched, so results stay usable.
"""

from __future__ import annotations

import re
from typing import Any

# The fields that carry what the documents say: page content, word / line /
# entity / relation-end text.
TEXT_KEYS = frozenset({"text", "content"})

_VISIBLE = re.compile(r"\S")


def mask(text: str) -> str:
    """Every character but whitespace becomes ``*`` (same length, same layout)."""
    return _VISIBLE.sub("*", text)


# What a purge hides on top: the name of the file.
PURGED_KEYS = TEXT_KEYS | {"filename"}


def purge_content(value: Any) -> Any:
    """A copy of ``value`` without what the documents said.

    Texts, contents and file names are masked like ``mask_text_fields`` does,
    and the key of a page image is dropped (the image itself is deleted from
    storage). Labels, scores, offsets, boxes and counts stay: they are what the
    statistics are made of.
    """
    if isinstance(value, dict):
        return {
            key: mask(item)
            if key in PURGED_KEYS and isinstance(item, str)
            else None
            if key == "s3_key"
            else purge_content(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [purge_content(item) for item in value]
    return value


def storage_keys(value: Any) -> set[str]:
    """Every object key (``s3_key``) that ``value`` points at."""
    if isinstance(value, dict):
        found = {v for k, v in value.items() if k == "s3_key" and isinstance(v, str)}
        for item in value.values():
            found |= storage_keys(item)
        return found
    if isinstance(value, list):
        return set().union(*(storage_keys(item) for item in value)) if value else set()
    return set()


def mask_text_fields(value: Any) -> Any:
    """A copy of ``value`` with every ``text`` / ``content`` string masked."""
    if isinstance(value, dict):
        return {
            key: mask(item)
            if key in TEXT_KEYS and isinstance(item, str)
            else mask_text_fields(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_text_fields(item) for item in value]
    return value
