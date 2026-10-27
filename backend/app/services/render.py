"""Render the pages of a finished file run, with what was found on them.

The pages are the parser's screenshots; the entities are the ner worker's
output. Both are read from the run's own tasks (never from anything the
caller sends), and only for the run's owner or an admin.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any
from uuid import UUID

import numpy as np
import supervision as sv
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.text_replacement import replacement_key
from app.repositories.page_bbox import PageBboxRepository
from app.repositories.run_edit import BoxOverrideRepository, TextReplacementRepository
from app.repositories.service import ServiceRepository
from app.repositories.task import TaskRepository
from app.schemas.render import RenderedDocument, RenderRequest
from app.services.exceptions import NotFoundError

# The services a run's steps run on (see app.services.run).
PARSER_SERVICE = "liteparse-ocr"
NER_SERVICE = "ner"

# A colour per entity label: same label, same colour, on every page.
_PALETTE = sv.ColorPalette.from_hex(
    [
        "#e6194b",
        "#3cb44b",
        "#4363d8",
        "#f58231",
        "#911eb4",
        "#46f0f0",
        "#f032e6",
        "#bcf60c",
        "#fabebe",
        "#008080",
        "#e6b800",
        "#9a6324",
        "#800000",
        "#808000",
        "#000075",
    ]
)


class RenderError(Exception):
    """The run cannot be rendered (no screenshots, no entities, bad pages)."""


def _pages_of(task: Task) -> list[dict[str, Any]]:
    return (task.output_data or {}).get("pages") or []


def _entities_of(task: Task) -> dict[int, list[dict[str, Any]]]:
    """The ner output, by page number."""
    out: dict[int, list[dict[str, Any]]] = {}
    for page in (task.output_data or {}).get("pages") or []:
        out[page.get("page_number")] = page.get("entities") or []
    return out


def _with_overrides(
    entities: dict[int, list[dict[str, Any]]],
    overrides: dict[tuple[int, str, int], dict[str, float]],
) -> dict[int, list[dict[str, Any]]]:
    """The entities, with the boxes users corrected in place of the detected ones."""
    if not overrides:
        return entities
    out: dict[int, list[dict[str, Any]]] = {}
    for number, items in entities.items():
        fixed = []
        for e in items:
            boxes = [
                overrides.get((number, e.get("id"), i), b)
                for i, b in enumerate(e.get("bboxes") or [])
            ]
            fixed.append({**e, "bboxes": boxes})
        out[number] = fixed
    return out


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # an old Pillow: only the fixed-size font
        return ImageFont.load_default()


def _write_replacement(img: Image.Image, boxes: list[list[float]], text: str) -> None:
    """Black on white, simple: every box is painted white and outlined; the
    text goes in the first one, as large as fits."""
    draw = ImageDraw.Draw(img)
    for x1, y1, x2, y2 in boxes:
        draw.rectangle(
            [x1, y1, x2, y2],
            fill="white",
            outline="black",
            width=max(1, int((y2 - y1) // 14)),
        )
    x1, y1, x2, y2 = boxes[0]
    pad = 3
    size = max(8, int((y2 - y1) * 0.7))
    font = _font(size)
    while size > 8:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= (x2 - x1) - 2 * pad:
            break
        size -= 1
        font = _font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (
            x1 + ((x2 - x1) - (right - left)) / 2 - left,
            y1 + ((y2 - y1) - (bottom - top)) / 2 - top,
        ),
        text,
        fill="black",
        font=font,
    )


def _selected(entity_ids: list[str] | None) -> set[str] | None:
    """The ids to keep, as "page:entity" pairs.

    Entity ids restart on every page (e0, e1, ...), so a bare id matches the
    same id on every page while "2:e0" matches e0 on page 2 only. Both forms
    can be mixed.
    """
    if not entity_ids:
        return None
    return set(entity_ids)


def _keeps(entity: dict[str, Any], page_number: int, keep: set[str] | None) -> bool:
    """Whether this entity of this page is selected."""
    if keep is None:
        return True
    eid = entity.get("id")
    return eid in keep or f"{page_number}:{eid}" in keep


def _pixel_boxes(entity: dict[str, Any], size: tuple[int, int]) -> list[list[float]]:
    """The entity's boxes (fractions of the page) as pixel [x1, y1, x2, y2]."""
    w, h = size
    out = []
    for b in entity.get("bboxes") or []:
        x1 = max(0.0, min(1.0, b.get("x", 0.0))) * w
        y1 = max(0.0, min(1.0, b.get("y", 0.0))) * h
        x2 = max(0.0, min(1.0, b.get("x", 0.0) + b.get("width", 0.0))) * w
        y2 = max(0.0, min(1.0, b.get("y", 0.0) + b.get("height", 0.0))) * h
        if x2 > x1 and y2 > y1:
            out.append([x1, y1, x2, y2])
    return out


class RenderService:
    """Turn a finished file run into downloadable pages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.services = ServiceRepository(session)
        self.bboxes = PageBboxRepository(session)
        self.replacements = TextReplacementRepository(session)
        self.overrides = BoxOverrideRepository(session)

    async def render(self, run_id: UUID, request: RenderRequest) -> RenderedDocument:
        run = await self.tasks.get(run_id)
        if run.purged_at is not None:
            raise RenderError("The content of this run was purged.")
        parser, ner = await self._children(run)
        pages = [p for p in _pages_of(parser) if p.get("s3_key")]
        if not pages:
            raise RenderError("This run has no page screenshots to render.")
        if run.status != TaskStatus.SUCCESS:
            raise RenderError("The run is not finished yet.")

        numbers = sorted(p.get("page_number") for p in pages)
        wanted = sorted(set(request.page_numbers or numbers))
        unknown = [n for n in wanted if n not in numbers]
        if unknown:
            raise RenderError(f"No page {unknown[0]} in this run.")
        if request.format == "png" and len(wanted) != 1:
            raise RenderError("PNG export takes exactly one page number.")
        pages = [p for p in pages if p.get("page_number") in wanted]

        corrected = {
            (o.page_number, o.entity_id, o.bbox_index): {
                "x": o.x,
                "y": o.y,
                "width": o.width,
                "height": o.height,
            }
            for o in await self.overrides.list_for_run(run_id)
        }
        entities = _with_overrides(_entities_of(ner), corrected)
        texts = (
            {r.key: r.replacement for r in await self.replacements.list_for_run(run_id)}
            if request.replace
            else {}
        )
        # The boxes users drew: blurred like entities, whatever the selection.
        drawn: dict[int, list[dict[str, Any]]] = {}
        for b in await self.bboxes.list_for_run(run_id):
            drawn.setdefault(b.page_number, []).append(
                {
                    "label": b.label or "manual",
                    "bboxes": [
                        {"x": b.x, "y": b.y, "width": b.width, "height": b.height}
                    ],
                }
            )
        rendered = [
            await self._render_page(
                p,
                entities.get(p.get("page_number")) or [],
                drawn.get(p.get("page_number")) or [],
                request,
                texts,
            )
            for p in pages
        ]
        return self._assemble(rendered, request)

    async def _children(self, run: Task) -> tuple[Task, Task]:
        """The run's parser and ner tasks, by the service they run on."""
        kids = await self.tasks.list_children(run.id)
        by_service: dict[str, Task] = {}
        for kid in kids:
            if kid.service_id is None:
                continue
            service = await self.services.get(kid.service_id)
            if service is not None:
                by_service.setdefault(service.name, kid)
        parser = by_service.get(PARSER_SERVICE)
        ner = by_service.get(NER_SERVICE)
        if parser is None or ner is None:
            raise RenderError("This run has no pages to render.")
        return parser, ner

    async def _render_page(
        self,
        page: dict[str, Any],
        entities: list[dict[str, Any]],
        drawn: list[dict[str, Any]],
        request: RenderRequest,
        texts: dict[str, str],
    ) -> tuple[int, Image.Image]:
        """One page: the stored screenshot, blurred and annotated as asked."""
        try:
            data = await storage.get_object(page["s3_key"])
        except storage.ObjectNotFoundError:
            raise RenderError(
                f"The image of page {page.get('page_number')} was deleted from storage."
            ) from None
        img = Image.open(io.BytesIO(data)).convert("RGB")

        if request.blur == "full":
            # The whole page: unreadable, but the layout stays recognisable.
            img = img.filter(ImageFilter.GaussianBlur(radius=img.width // 25))
            return page.get("page_number"), img

        if request.blur == "entities" or request.boxes:
            img = self._annotate(
                img, entities, drawn, page.get("page_number"), request, texts
            )
        return page.get("page_number"), img

    def _annotate(
        self,
        img: Image.Image,
        entities: list[dict[str, Any]],
        drawn: list[dict[str, Any]],
        page_number: int,
        request: RenderRequest,
        texts: dict[str, str],
    ) -> Image.Image:
        """Blur, replace and/or box the kept entities, with supervision."""
        keep = _selected(request.entity_ids)
        kept = (
            [e for e in entities if _keeps(e, page_number, keep)]
            if request.entities
            else []
        ) + drawn
        boxes: list[list[float]] = []
        labels: list[str] = []
        # The entities with a replacement are written over, not blurred.
        replaced: list[tuple[list[list[float]], str]] = []
        blurred: list[bool] = []
        for e in kept:
            text = None
            if request.blur == "entities":
                text = texts.get(replacement_key(e.get("text") or ""))
            own = _pixel_boxes(e, img.size)
            if text and own:
                replaced.append((own, text))
            for box in own:
                boxes.append(box)
                labels.append(e.get("label", ""))
                blurred.append(not text)
        if not boxes:
            return img

        # One colour per distinct label, so the same kind of entity looks the
        # same everywhere (and the label above the box matches).
        names = sorted(set(labels))
        palette = sv.ColorPalette(
            [_PALETTE.colors[i % len(_PALETTE)] for i, _ in enumerate(names)]
        )
        class_of = {n: i for i, n in enumerate(names)}
        detections = sv.Detections(
            xyxy=np.array(boxes, dtype=np.float32),
            class_id=np.array([class_of[l] for l in labels], dtype=int),
        )
        scene = np.array(img)
        if request.blur == "entities" and any(blurred):
            scene = sv.BlurAnnotator(kernel_size=25).annotate(
                scene=scene, detections=detections[np.array(blurred)]
            )
        if replaced:
            out = Image.fromarray(scene)
            for own, text in replaced:
                _write_replacement(out, own, text)
            scene = np.array(out)
        if request.boxes:
            scene = sv.BoxAnnotator(color=palette).annotate(
                scene=scene, detections=detections
            )
            # The label sits above its box, on the box's colour.
            scene = sv.LabelAnnotator(color=palette).annotate(
                scene=scene, detections=detections, labels=labels
            )
        return Image.fromarray(scene)

    def _assemble(
        self, rendered: list[tuple[int, Image.Image]], request: RenderRequest
    ) -> RenderedDocument:
        if request.format == "png":
            buf = io.BytesIO()
            rendered[0][1].save(buf, format="PNG")
            return RenderedDocument(
                data=buf.getvalue(),
                media_type="image/png",
                filename=f"page-{rendered[0][0]}.png",
            )
        if request.format == "pdf":
            buf = io.BytesIO()
            first, *rest = [img for _, img in rendered]
            first.save(buf, format="PDF", save_all=True, append_images=rest)
            return RenderedDocument(
                data=buf.getvalue(), media_type="application/pdf", filename="pages.pdf"
            )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for number, img in rendered:
                page_buf = io.BytesIO()
                img.save(page_buf, format="PNG")
                zf.writestr(f"page-{number}.png", page_buf.getvalue())
        return RenderedDocument(
            data=buf.getvalue(), media_type="application/zip", filename="pages.zip"
        )


async def get_run_or_404(session: AsyncSession, run_id: UUID) -> Task:
    """The run task, or a 404 that does not reveal whether it exists."""
    task = await TaskRepository(session).get(run_id)
    if task is None:
        raise NotFoundError(f"Task {run_id} not found.")
    return task
