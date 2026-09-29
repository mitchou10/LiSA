"""Parser service: text, OCR and word boxes from PDFs and images.

Built on LiteParse (native text extraction, Tesseract OCR only where a page has
no text layer). For every page it returns:

* ``content``: the page text, one line per text line,
* ``lines`` / ``words``: boxes in page coordinates (``width`` x ``height``),
  each carrying ``start``/``end`` character offsets into ``content`` so that an
  entity found by an analyser (``start_char``/``end_char``) can be mapped back
  onto the page,
* ``image``: a PNG data URL of the rendered page.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
import re
import tempfile
import uuid
from typing import Any

from liteparse import LiteParse
from PIL import Image, ImageFilter
from worker.core.services.base import BaseService, TaskStatus

from app import config

logger = logging.getLogger("lisa.service.parser")

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "ParserInput",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "mime": {"type": ["string", "null"]},
                    "data_base64": {"type": "string"},
                },
                "required": ["filename", "data_base64"],
            },
        },
        "blur_screenshots": {"type": "boolean", "default": False},
    },
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "ParsedDocuments",
    "properties": {
        "id": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "filename": {"type": "string"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "content": {"type": "string"},
                    "lines": {"type": "array"},
                    "words": {"type": "array"},
                    "image": {"type": ["string", "null"]},
                },
            },
        },
        "error": {"type": ["string", "null"]},
    },
}

_TOKEN_RE = re.compile(r"\S+")
_EXT_BY_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
}


def blur_png(image_bytes: bytes) -> bytes:
    """Irreversibly blur a page image so its text can no longer be read.

    The radius scales with the image so that text-sized details vanish at any
    resolution. The original pixels are never returned or stored.
    """
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        radius = max(config.BLUR_MIN_RADIUS, min(image.size) * config.BLUR_RATIO)
        out = io.BytesIO()
        image.filter(ImageFilter.GaussianBlur(radius)).save(out, format="PNG")
        return out.getvalue()


class ParserError(ValueError):
    """The file cannot be processed (bad payload, too large, unsupported)."""


def _decode(data_base64: str) -> bytes:
    """Decode plain base64 or a ``data:...;base64,`` URL."""
    if data_base64.startswith("data:"):
        data_base64 = data_base64.partition(",")[2]
    try:
        return base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ParserError("Invalid base64 payload.") from exc


def _suffix(filename: str, mime: str | None) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return ext or _EXT_BY_MIME.get((mime or "").lower(), "")


def _word_boxes(item: Any, line_start: int) -> list[dict[str, Any]]:
    """Word boxes of one text line, with offsets relative to the page text.

    Uses the boxes LiteParse provides; OCR lines come without word boxes, so
    the line box is split proportionally to each word's position in the text.
    """
    text = item.text
    boxes: list[dict[str, Any]] = []
    if item.words:
        cursor = 0
        for w in item.words:
            idx = text.find(w.text, cursor)
            if idx < 0:
                continue
            cursor = idx + len(w.text)
            boxes.append(
                {
                    "text": w.text,
                    "x": w.x,
                    "y": w.y,
                    "width": w.width,
                    "height": w.height,
                    "start": line_start + idx,
                    "end": line_start + cursor,
                }
            )
        if boxes:
            return boxes
    total = max(len(text), 1)
    for m in _TOKEN_RE.finditer(text):
        boxes.append(
            {
                "text": m.group(),
                "x": item.x + item.width * m.start() / total,
                "y": item.y,
                "width": item.width * (m.end() - m.start()) / total,
                "height": item.height,
                "start": line_start + m.start(),
                "end": line_start + m.end(),
            }
        )
    return boxes


def build_page(parsed_page: Any) -> dict[str, Any]:
    """Convert a LiteParse page into our page dict (without image/filename)."""
    lines: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    parts: list[str] = []
    cursor = 0
    for item in parsed_page.text_items:
        text = item.text
        if not text.strip():
            continue
        start = cursor
        lines.append(
            {
                "text": text,
                "x": item.x,
                "y": item.y,
                "width": item.width,
                "height": item.height,
                "start": start,
                "end": start + len(text),
                "confidence": item.confidence,
            }
        )
        words.extend(_word_boxes(item, start))
        parts.append(text)
        cursor = start + len(text) + 1  # "\n" separator
    return {
        "width": parsed_page.width,
        "height": parsed_page.height,
        "content": "\n".join(parts),
        "lines": lines,
        "words": words,
    }


class ParserService(BaseService):
    """OCR/parsing worker producing page images, text and word boxes."""

    name = "liteparse-ocr"
    version = "0.1.0"
    description = (
        "Document parsing and OCR (Tesseract via LiteParse): renders pages and "
        "extracts text with word bounding boxes from PDFs and images."
    )
    tags = ["ocr", "tesseract", "liteparse", "pdf", "image", "bbox"]
    type = "other"
    queue = config.CELERY_QUEUE
    input_schema = INPUT_SCHEMA
    output_schema = OUTPUT_SCHEMA

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._parser: LiteParse | None = None

    def _get_parser(self) -> LiteParse:
        if self._parser is None:
            self._parser = LiteParse(
                ocr_language=config.OCR_LANGUAGE,
                emit_word_boxes=True,
                max_pages=config.MAX_PAGES,
                quiet=True,
            )
        return self._parser

    def parse_file(
        self, filename: str, mime: str | None, data: bytes, *, blur: bool = False
    ) -> list[dict[str, Any]]:
        """Parse one file into page dicts (image included, blurred on demand)."""
        max_bytes = config.MAX_FILE_MB * 1024 * 1024
        if len(data) > max_bytes:
            raise ParserError(
                f"'{filename}' exceeds the {config.MAX_FILE_MB:g} MB limit."
            )
        suffix = _suffix(filename, mime)
        parser = self._get_parser()
        # LiteParse detects the format from the extension, so work on a file.
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            try:
                result = parser.parse(tmp.name)
                shots = {s.page_num: s for s in parser.screenshot(tmp.name)}
            except Exception as exc:  # noqa: BLE001 - surface a clean message
                raise ParserError(f"Cannot parse '{filename}': {exc}") from exc

        pages: list[dict[str, Any]] = []
        for parsed in result.pages[: config.MAX_PAGES]:
            page = build_page(parsed)
            shot = shots.get(parsed.page_num)
            image_bytes = (
                (blur_png(shot.image_bytes) if blur else shot.image_bytes)
                if shot
                else None
            )
            page.update(
                {
                    "filename": filename,
                    "source_page": parsed.page_num,
                    "image": (
                        "data:image/png;base64," + base64.b64encode(image_bytes).decode()
                        if image_bytes
                        else None
                    ),
                    "blurred": blur,
                }
            )
            pages.append(page)
        return pages

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        files = (input_data or {}).get("files") if isinstance(input_data, dict) else None
        blur = bool(input_data.get("blur_screenshots")) if isinstance(input_data, dict) else False
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            if not files:
                raise ParserError("No file provided (expected input 'files').")
            pages: list[dict[str, Any]] = []
            for index, f in enumerate(files):
                data = _decode(f.get("data_base64", ""))
                for page in self.parse_file(
                    f.get("filename") or f"file-{index + 1}", f.get("mime"), data, blur=blur
                ):
                    page["page_number"] = len(pages) + 1
                    pages.append(page)
                self.update_task(task_id, progress=round((index + 1) / len(files) * 100))
        except Exception as exc:  # noqa: BLE001 - mark the task failed and re-raise
            self._scrub_input(task_id, files)
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = {"id": task_id or f"parser-{uuid.uuid4()}", "pages": pages, "error": None}
        self._scrub_input(task_id, files)
        self.update_task(task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result)
        return result

    def _scrub_input(self, task_id: str | None, files: Any) -> None:
        """Drop the uploaded bytes from the stored task (keeps polls light)."""
        if not task_id or not files:
            return
        summary = {
            "files": [
                {"filename": f.get("filename"), "mime": f.get("mime")} for f in files
            ]
        }
        try:
            self._tasks.update(task_id, {"input_data": summary})
        except Exception as exc:  # noqa: BLE001 - best effort
            logger.warning("Could not scrub input of task %s: %s", task_id, exc)
