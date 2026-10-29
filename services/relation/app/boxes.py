"""Map a character span of a page onto boxes of the page."""

from __future__ import annotations

from app.schemas import Box, InputWord


def _across(word: InputWord) -> tuple[float, float]:
    """Where the word sits across its line, and how thick the line is.

    Text turned 90 or 270 degrees runs vertically, so its lines are told apart
    by their x, not their y.
    """
    if word.angle in (90, 270):
        return word.x, word.width
    return word.y, word.height


def boxes_for_span(
    words: list[InputWord],
    start: int,
    end: int,
    *,
    content: str = "",
    line_tolerance: float = 0.5,
) -> list[Box]:
    """One box per visual line covered by ``[start, end)``.

    Takes the words overlapping the span, groups the ones that sit on the same
    line (same text angle, and an overlap across the line above
    ``line_tolerance`` of the smaller thickness) and returns the union of each
    group, with the angle of its text. Given the page ``content``, each box also
    says which part of the span it covers (``text``, ``start``, ``end``).
    """
    hit = sorted(
        (w for w in words if w.start < end and w.end > start),
        key=lambda w: (w.angle, _across(w)[0], w.x, w.y),
    )
    groups: list[list[InputWord]] = []
    for word in hit:
        ref = groups[-1][0] if groups else None
        if ref and ref.angle == word.angle:
            (pos, size), (ref_pos, ref_size) = _across(word), _across(ref)
            if abs(pos - ref_pos) < min(size, ref_size) * line_tolerance:
                groups[-1].append(word)
                continue
        groups.append([word])
    boxes = []
    for group in groups:
        x1 = min(w.x for w in group)
        y1 = min(w.y for w in group)
        x2 = max(w.x + w.width for w in group)
        y2 = max(w.y + w.height for w in group)
        first = max(start, min(w.start for w in group))
        last = min(end, max(w.end for w in group))
        boxes.append(
            Box(
                x=x1,
                y=y1,
                width=x2 - x1,
                height=y2 - y1,
                angle=group[0].angle,
                text=content[first:last] if content else None,
                start=first,
                end=last,
            )
        )
    return boxes
