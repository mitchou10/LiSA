"""Map a character span of a page onto boxes of the page."""

from __future__ import annotations

from app.schemas import Box, InputWord


def boxes_for_span(
    words: list[InputWord], start: int, end: int, *, line_tolerance: float = 0.5
) -> list[Box]:
    """One box per visual line covered by ``[start, end)``.

    Takes the words overlapping the span, groups the ones that sit on the same
    line (vertical overlap above ``line_tolerance`` of the smaller height) and
    returns the union of each group.
    """
    hit = sorted(
        (w for w in words if w.start < end and w.end > start),
        key=lambda w: (w.y, w.x),
    )
    groups: list[list[InputWord]] = []
    for word in hit:
        ref = groups[-1][0] if groups else None
        if ref and abs(word.y - ref.y) < min(ref.height, word.height) * line_tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    boxes = []
    for group in groups:
        x1 = min(w.x for w in group)
        y1 = min(w.y for w in group)
        x2 = max(w.x + w.width for w in group)
        y2 = max(w.y + w.height for w in group)
        boxes.append(Box(x=x1, y=y1, width=x2 - x1, height=y2 - y1))
    return boxes
