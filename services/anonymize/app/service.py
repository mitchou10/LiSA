"""Anonymize service v2: redact spans and boxes already detected upstream.

Unlike the llm-guard version, nothing is detected here. ``process`` receives
pages plus the spans / boxes to anonymize (``anonymized_pages``) and returns
the pages with the spans redacted. Progress and status are reported to the
backend task as pages are processed.
"""

from __future__ import annotations

import io
import re
from typing import Any
from urllib.parse import urlparse

import boto3
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field
from worker.core.services.base import BaseService, TaskStatus

from app import config


class Bbox(BaseModel):
    """Box relative to the page image: every value is between 0 and 1."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)
    text: str | None = None
    label: str


class Page(BaseModel):
    content: str
    page_number: int | None = None
    bboxes: list[Bbox] = Field(default_factory=list)
    # Image of the page in object storage: its key in the configured bucket
    # (what the parser returns)...
    s3_key: str | None = None
    # ...or a full "s3://bucket/key" / "http(s)://host/bucket/key" URL.
    page_url: str | None = None


class Span(BaseModel):
    start: int
    end: int
    text: str
    # Shown in place of the span, in upper case: "person" -> "[PERSON]".
    label: str


class AnonymizedPage(BaseModel):
    page_number: int
    bboxes: list[Bbox] = Field(default_factory=list)
    span: list[Span] = Field(default_factory=list)


class InputData(BaseModel):
    pages: list[Page] = Field(default_factory=list)
    anonymized_pages: list[AnonymizedPage] = Field(default_factory=list)
    # True: all text becomes "*" (spans get a visible [LABEL] marker) and the page
    # images in S3 are replaced by a blurred copy with the labelled boxes.
    # False: only the spans get the marker and images are left untouched.
    blurred: bool = False


class OutputData(BaseModel):
    pages: list[Page] = Field(default_factory=list)


def marker(span: Span) -> str:
    return f"[{span.label.upper()}]"


def redact(content: str, spans: list[Span], *, blurred: bool) -> str:
    """Mark every span in ``content``; with ``blurred``, star out the rest.

    ``blurred``: all text becomes ``*`` (whitespace is kept, so lines and word
    breaks survive) and each span is replaced by a visible marker, its label in
    upper case (``[PERSON]``). Otherwise only the spans are replaced.

    Spans are applied from the end of the text so earlier offsets stay valid;
    a span overlapping one already applied is clipped to what is left.
    """
    if blurred:
        content = re.sub(r"\S", "*", content)
    limit = len(content)
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        start, end = max(0, span.start), min(span.end, limit)
        if start >= end:
            continue
        content = content[:start] + marker(span) + content[end:]
        limit = start
    return content


def parse_s3_location(url: str, default_bucket: str) -> tuple[str, str]:
    """Split a page image URL into ``(bucket, key)``."""
    parsed = urlparse(url)
    if parsed.scheme == "s3":
        return parsed.netloc, parsed.path.lstrip("/")
    if parsed.scheme in ("http", "https"):
        path = parsed.path.lstrip("/")
        bucket, _, key = path.partition("/")
        if default_bucket and bucket != default_bucket:
            # Virtual-host style or unknown layout: keep the configured bucket.
            return default_bucket, path
        return bucket, key
    raise ValueError(f"Unsupported page_url: {url!r}")


def blur_and_annotate(
    image_bytes: bytes,
    bboxes: list[Bbox],
) -> tuple[bytes, str]:
    """Blur the whole image, then draw each bbox with its label on top.

    Boxes are relative (0-1) and are converted to the image's pixels here.

    Returns the encoded image and its MIME type. The original format is kept
    (PNG when it cannot be determined).
    """
    with Image.open(io.BytesIO(image_bytes)) as source:
        fmt = source.format or "PNG"
        image = source.convert("RGB")
    radius = max(
        config.settings.BLUR_MIN_RADIUS, min(image.size) * config.settings.BLUR_RATIO
    )
    image = image.filter(ImageFilter.GaussianBlur(radius))

    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(12, round(min(image.size) * 0.02)))
    img_w, img_h = image.size
    for box in bboxes:
        left, top = box.x * img_w, box.y * img_h
        right, bottom = left + box.width * img_w, top + box.height * img_h
        draw.rectangle((left, top, right, bottom), outline=(220, 38, 38), width=3)
        label_box = draw.textbbox((left, top), box.label, font=font)
        pad = 2
        # Label sits just above the box, or inside it when at the very top.
        shift = (label_box[3] - label_box[1]) + 2 * pad
        dy = -shift if top - shift >= 0 else 0
        draw.rectangle(
            (
                label_box[0] - pad,
                label_box[1] + dy - pad,
                label_box[2] + pad,
                label_box[3] + dy + pad,
            ),
            fill=(220, 38, 38),
        )
        draw.text((left, top + dy), box.label, fill=(255, 255, 255), font=font)

    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue(), Image.MIME.get(fmt, "image/png")


class AnonymizeServiceV2(BaseService):
    name = "anonymize-v2"
    version = "0.1.0"
    description = "Redacts spans and boxes already detected by an analyser."
    # Must match the queue the Celery worker consumes (see app.celery_app).
    queue = config.settings.CELERY_QUEUE
    tags = ["anonymize", "v2"]
    type = "guard"
    input_schema = InputData.model_json_schema()
    output_schema = OutputData.model_json_schema()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._s3: Any = None

    @property
    def s3_client(self) -> Any:
        """Built on first use, so the service starts without S3 configured."""
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                aws_access_key_id=config.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.settings.AWS_SECRET_ACCESS_KEY,
                region_name=config.settings.AWS_S3_REGION or None,
                endpoint_url=config.settings.AWS_S3_ENDPOINT_URL or None,
            )
        return self._s3

    def _blur_page_image(self, page: Page, bboxes: list[Bbox]) -> None:
        """Replace the page image in S3 by its blurred copy with labelled boxes."""
        if page.s3_key:
            bucket, key = config.settings.AWS_S3_BUCKET, page.s3_key
        else:
            bucket, key = parse_s3_location(
                page.page_url, config.settings.AWS_S3_BUCKET
            )
        original = self.s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
        data, content_type = blur_and_annotate(original, bboxes)
        self.s3_client.put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type
        )

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            data = InputData.model_validate(input_data or {})
            pages = {page.page_number: page for page in data.pages}
            total = len(data.anonymized_pages) or 1
            for index, anonymized in enumerate(data.anonymized_pages):
                page = pages.get(anonymized.page_number)
                if page is not None:
                    page.content = redact(
                        page.content, anonymized.span, blurred=data.blurred
                    )
                    if data.blurred and (page.s3_key or page.page_url):
                        self._blur_page_image(page, anonymized.bboxes)
                self.update_task(task_id, progress=round((index + 1) / total * 100))
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = OutputData(pages=data.pages).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
