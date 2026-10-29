"""Parser service: text, OCR, boxes and screenshots from PDFs and images.

Built on LiteParse (native text extraction, Tesseract OCR only where a page has
no text layer). The service reads each file from the bucket by its ``s3_key``,
deletes it right away, and returns for every page the text and the relative
boxes in clear (see ``app.schemas.Page``) plus the ``s3_key`` of a screenshot
that is blurred by default. Detection and anonymization happen elsewhere.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Any

from liteparse import LiteParse
from pydantic import ValidationError
from worker.core.services.base import BaseService, TaskStatus

from app.config import settings
from app.errors import ParserError, StorageError
from app.imaging import blur_png, rotate_box, upright_png
from app.layout import build_page
from app.paddle import OCR_MODEL as PADDLE_MODEL
from app.paddle import PaddleEngine
from app.schemas import InputFile, ParserInput, ParserOutput
from app.storage import Storage

logger = logging.getLogger("lisa.service.parser")

_EXT_BY_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
}


def _suffix(filename: str, mime: str | None) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return ext or _EXT_BY_MIME.get((mime or "").lower(), "")


def _is_scanned(parsed: Any) -> bool:
    """A page without any text layer: only OCR can read it."""
    return not any(item.text.strip() for item in parsed.text_items)


class ParserService(BaseService):
    """OCR/parsing worker producing text, relative boxes and screenshots."""

    name = "liteparse-ocr"
    version = "0.1.0"
    description = (
        "Document parsing and OCR (LiteParse, with Tesseract or PaddleOCR and page "
        "orientation detection): extracts text with relative word boxes and stores "
        "a (blurred) screenshot of each page."
    )
    tags = [
        "ocr",
        "tesseract",
        "paddleocr",
        "orientation",
        "liteparse",
        "pdf",
        "image",
        "bbox",
    ]
    type = "other"
    queue = settings.CELERY_QUEUE
    input_schema = ParserInput.model_json_schema()
    output_schema = ParserOutput.model_json_schema()

    def __init__(
        self,
        *,
        storage: Storage | None = None,
        paddle: PaddleEngine | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.storage = storage or Storage()
        self.paddle = paddle or PaddleEngine()
        self._parser: LiteParse | None = None

    def _get_parser(self) -> LiteParse:
        if self._parser is None:
            self._parser = LiteParse(
                ocr_language=settings.OCR_LANGUAGE,
                emit_word_boxes=True,
                max_pages=settings.MAX_PAGES,
                quiet=True,
            )
        return self._parser

    def _parse_with_paddle(
        self, path: str
    ) -> tuple[Any, dict[int, Any], dict[int, int]]:
        """LiteParse without OCR, then the orientation of the scanned pages.

        Returns the parse result, the page screenshots and the rotation found
        per page. Nothing is turned: text, boxes and screenshots stay in the
        orientation of the source, and each box says its text's angle. The
        text layer is read by LiteParse; the pages without one are read by
        PaddleOCR in ``parse_file``.
        """
        native = LiteParse(
            ocr_enabled=False,
            emit_word_boxes=True,
            max_pages=settings.MAX_PAGES,
            quiet=True,
        )
        result = native.parse(path)
        shots = {s.page_num: s for s in native.screenshot(path)}
        angles = {
            page.page_num: self.paddle.orientation(shots[page.page_num].image_bytes)
            for page in result.pages[: settings.MAX_PAGES]
            if page.page_num in shots and _is_scanned(page)
        }
        return result, shots, angles

    def _ocr_page(self, parsed: Any, image_bytes: bytes, angle: int) -> Any:
        """PaddleOCR lines of a page image, in the page's own units.

        The page is read upright; the boxes are then mapped back onto the page
        as it is, and carry the ``angle`` of their text.
        """
        items, (img_w, img_h) = self.paddle.read(
            upright_png(image_bytes, angle) if angle else image_bytes
        )
        for item in items:
            x, y, w, h = rotate_box(
                (
                    item.x / img_w,
                    item.y / img_h,
                    item.width / img_w,
                    item.height / img_h,
                ),
                angle,
            )
            item.x, item.width = x * parsed.width, w * parsed.width
            item.y, item.height = y * parsed.height, h * parsed.height
            item.angle = angle
        return items

    def parse_file(
        self,
        filename: str,
        mime: str | None,
        data: bytes,
        *,
        key_prefix: str,
        blur: bool = True,
    ) -> list[dict[str, Any]]:
        """Parse one file into pages.

        Each screenshot (PNG, blurred unless ``blur`` is false) is uploaded to
        ``<key_prefix>/<source page>.png`` straight away: pages only carry its
        ``s3_key``, never the image bytes, and the unblurred pixels never leave
        this method.
        """
        self.storage.require_configured()
        max_bytes = settings.MAX_FILE_MB * 1024 * 1024
        if len(data) > max_bytes:
            raise ParserError(
                f"'{filename}' exceeds the {settings.MAX_FILE_MB:g} MB limit."
            )
        use_paddle = settings.OCR_ENGINE == "paddleocr"
        angles: dict[int, int] = {}
        # LiteParse detects the format from the extension, so work on a file.
        with tempfile.NamedTemporaryFile(suffix=_suffix(filename, mime)) as tmp:
            tmp.write(data)
            tmp.flush()
            try:
                if use_paddle:
                    result, shots, angles = self._parse_with_paddle(tmp.name)
                else:
                    parser = self._get_parser()
                    result = parser.parse(tmp.name)
                    shots = {s.page_num: s for s in parser.screenshot(tmp.name)}
            except ParserError:
                raise
            except Exception as exc:
                raise ParserError(f"Cannot parse '{filename}': {exc}") from exc

        pages: list[dict[str, Any]] = []
        for parsed in result.pages[: settings.MAX_PAGES]:
            shot = shots.get(parsed.page_num)
            if use_paddle:
                # No text layer: read the (unblurred) screenshot with PaddleOCR.
                angle = angles.get(parsed.page_num, 0)
                try:
                    items = (
                        self._ocr_page(parsed, shot.image_bytes, angle)
                        if shot and _is_scanned(parsed)
                        else None
                    )
                except ParserError:
                    raise
                except Exception as exc:
                    raise ParserError(f"Cannot read '{filename}': {exc}") from exc
                page = build_page(parsed, ocr_model=PADDLE_MODEL, items=items)
                page.orientation = angle
            else:
                page = build_page(parsed)
            if shot:
                png = blur_png(shot.image_bytes) if blur else shot.image_bytes
                page.s3_key = self.storage.write_png(
                    f"{key_prefix}/{parsed.page_num}.png", png
                )
            page.filename = filename
            page.source_page = parsed.page_num
            page.blurred = blur
            pages.append(page.model_dump())
        return pages

    def _read_source(self, spec: InputFile) -> bytes:
        """Read a source file, then delete it: the bytes are in memory."""
        data = self.storage.read(spec.s3_key)
        if settings.DELETE_SOURCE_AFTER_PARSE:
            try:
                self.storage.delete(spec.s3_key)
            except StorageError as exc:
                logger.warning("%s", exc)
        return data

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = ParserInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise ParserError(f"Invalid input: {exc}") from exc
            if not request.files:
                raise ParserError("No file provided (expected input 'files').")
            # Checked before reading, so a misconfiguration never costs a source.
            self.storage.require_configured()
            blur = (
                settings.BLUR_SCREENSHOTS
                if request.blur_screenshots is None
                else request.blur_screenshots
            )
            pages: list[dict[str, Any]] = []
            prefix = f"pages/{task_id or uuid.uuid4()}"
            for index, spec in enumerate(request.files):
                data = self._read_source(spec)
                for page in self.parse_file(
                    spec.filename or os.path.basename(spec.s3_key),
                    spec.mime,
                    data,
                    key_prefix=f"{prefix}/{index + 1}",
                    blur=blur,
                ):
                    page["page_number"] = len(pages) + 1
                    pages.append(page)
                self.update_task(
                    task_id, progress=round((index + 1) / len(request.files) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = ParserOutput(
            id=task_id or f"parser-{uuid.uuid4()}", pages=pages
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
