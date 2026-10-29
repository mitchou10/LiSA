"""Input and output contracts of the parser (advertised to the backend)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InputFile(BaseModel):
    s3_key: str = Field(description="Key of the file in the bucket (S3_BUCKET).")
    filename: str | None = Field(
        default=None,
        description="Original name; its extension tells the format "
        "(defaults to the last part of the key).",
    )
    mime: str | None = None


class ParserInput(BaseModel):
    files: list[InputFile] = Field(default_factory=list)
    blur_screenshots: bool | None = Field(
        default=None,
        description="Blur the screenshots. Defaults to BLUR_SCREENSHOTS (on).",
    )


class Box(BaseModel):
    """A box relative to the page: every value is a 0-1 fraction, origin top-left."""

    x: float
    y: float
    width: float
    height: float
    # Engine that produced the box: "liteparse" (native text layer),
    # "tesseract" or "paddleocr" (OCR).
    model: str


class Word(Box):
    text: str
    # Character offsets into the page ``content``.
    start: int
    end: int


class Line(Word):
    confidence: float | None = None


class Page(BaseModel):
    page_number: int = 0
    filename: str = ""
    source_page: int = 0
    # Page size in page units (e.g. PDF points), to recover absolute positions.
    width: float
    height: float
    content: str
    lines: list[Line] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)
    blurred: bool = True
    # Clockwise rotation (0, 90, 180 or 270) the page had in the source and
    # that was undone: text, boxes and screenshot are upright. Detected with
    # PaddleOCR only, otherwise 0.
    orientation: int = 0
    s3_key: str | None = Field(
        default=None, description="Key of the page screenshot in the bucket."
    )


class ParserOutput(BaseModel):
    id: str
    pages: list[Page] = Field(default_factory=list)
    error: str | None = None
