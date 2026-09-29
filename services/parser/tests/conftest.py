"""Shared fixtures: small real PDF and PNG documents generated on the fly."""

from __future__ import annotations

import base64
import io

import pytest


@pytest.fixture
def pdf_bytes() -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Contact John Doe at john@example.com")
    c.drawString(72, 690, "API key: sk-1234567890abcdef")
    c.showPage()
    c.drawString(72, 700, "Page two text")
    c.save()
    return buf.getvalue()


@pytest.fixture
def png_bytes() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 200), "white")
    font = None
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            font = ImageFont.truetype(path, 40)
            break
        except OSError:
            continue
    ImageDraw.Draw(image).text(
        (20, 60), "Scanned: Marie Curie 0612345678", fill="black", font=font
    )
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()
