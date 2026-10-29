"""Turn a LiteParse page into text plus relative boxes."""

from __future__ import annotations

import re
from typing import Any

from app.schemas import Line, Page, Word

_TOKEN_RE = re.compile(r"\S+")

NATIVE_MODEL = "liteparse"
OCR_MODEL = "tesseract"


def _unit(value: float, size: float) -> float:
    """Fraction of ``size``, clamped to 0-1."""
    return min(1.0, max(0.0, value / size)) if size > 0 else 0.0


def _word_boxes(
    item: Any, line_start: int, page_w: float, page_h: float, model: str, angle: int
) -> list[Word]:
    """Word boxes of one text line, with offsets relative to the page text.

    Uses the boxes LiteParse provides; OCR lines come without word boxes, so
    the line box is split proportionally to each word's position in the text.
    """
    text = item.text

    def word(t: str, x: float, y: float, w: float, h: float, a: int, b: int) -> Word:
        return Word(
            text=t,
            x=_unit(x, page_w),
            y=_unit(y, page_h),
            width=_unit(w, page_w),
            height=_unit(h, page_h),
            start=line_start + a,
            end=line_start + b,
            model=model,
            angle=angle,
        )

    boxes: list[Word] = []
    cursor = 0
    for w in item.words or []:
        idx = text.find(w.text, cursor)
        if idx < 0:
            continue
        cursor = idx + len(w.text)
        boxes.append(word(w.text, w.x, w.y, w.width, w.height, idx, cursor))
    if boxes:
        return boxes

    total = max(len(text), 1)
    out = []
    for m in _TOKEN_RE.finditer(text):
        # The share of the line this word covers, along the direction of the text.
        a, b = m.start() / total, m.end() / total
        if angle in (180, 270):
            a, b = 1 - b, 1 - a
        if angle in (90, 270):
            x, y, w, h = (
                item.x,
                item.y + item.height * a,
                item.width,
                item.height * (b - a),
            )
        else:
            x, y, w, h = (
                item.x + item.width * a,
                item.y,
                item.width * (b - a),
                item.height,
            )
        out.append(word(m.group(), x, y, w, h, m.start(), m.end()))
    return out


def build_page(
    parsed_page: Any, *, ocr_model: str = OCR_MODEL, items: list[Any] | None = None
) -> Page:
    """Convert a LiteParse page into a ``Page`` (no filename / screenshot yet).

    ``items`` replaces the page's own text items (OCR lines in page units);
    ``ocr_model`` names the engine behind the items that carry a confidence.
    """
    width, height = parsed_page.width, parsed_page.height
    lines: list[Line] = []
    words: list[Word] = []
    parts: list[str] = []
    cursor = 0
    for item in parsed_page.text_items if items is None else items:
        text = item.text
        if not text.strip():
            continue
        # No OCR confidence means the text came from the PDF's own text layer.
        model = NATIVE_MODEL if item.confidence is None else ocr_model
        angle = getattr(item, "angle", 0)
        lines.append(
            Line(
                text=text,
                x=_unit(item.x, width),
                y=_unit(item.y, height),
                width=_unit(item.width, width),
                height=_unit(item.height, height),
                start=cursor,
                end=cursor + len(text),
                confidence=item.confidence,
                model=model,
                angle=angle,
            )
        )
        words.extend(_word_boxes(item, cursor, width, height, model, angle))
        parts.append(text)
        cursor += len(text) + 1  # "\n" separator
    return Page(
        width=width,
        height=height,
        content="\n".join(parts),
        lines=lines,
        words=words,
    )
