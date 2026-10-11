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
