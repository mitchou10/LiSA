"""Render the pages of a finished file run: blurred, annotated, downloadable."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# What to blur on the exported pages.
# - "none": the pages as the parser stored them.
# - "entities": only the boxes of the selected entities (all of them when
#   none is selected).
# - "full": the whole page(s), everything on it becomes unreadable.
BlurMode = Literal["none", "entities", "full"]

# How the pages come back: one PNG, every page in a ZIP, or one PDF.
RenderFormat = Literal["png", "zip", "pdf"]


class RenderRequest(BaseModel):
    """What to render, and how.

    ``page_numbers``: the pages to export (None or []: all of them). ``png``
    needs exactly one page; ``zip`` and ``pdf`` take all the pages asked for.
    ``entity_ids``: the entities to blur or draw (None or []: all of them).
    ``blur``: nothing, the entities' boxes, or the whole page.
    ``entities``: False leaves the entities alone (only the boxes users drew
    are blurred); ``entity_ids`` is then ignored.
    ``boxes``: draw each kept entity's box with its label above it.
    """

    page_numbers: list[int] | None = None
    entity_ids: list[str] | None = None
    entities: bool = True
    blur: BlurMode = "entities"
    boxes: bool = False
    format: RenderFormat = "png"


class RenderedDocument(BaseModel):
    """The rendered bytes, ready to be returned as a download."""

    data: bytes
    media_type: str
    filename: str
