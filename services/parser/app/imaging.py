"""Page image helpers."""

from __future__ import annotations

import io

from PIL import Image, ImageFilter

from app.config import settings


def blur_png(image_bytes: bytes) -> bytes:
    """Irreversibly blur a page image so its text can no longer be read.

    The radius scales with the image so that text-sized details vanish at any
    resolution. The original pixels are never returned or stored.
    """
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        radius = max(settings.BLUR_MIN_RADIUS, min(image.size) * settings.BLUR_RATIO)
        out = io.BytesIO()
        image.filter(ImageFilter.GaussianBlur(radius)).save(out, format="PNG")
        return out.getvalue()


def upright_png(image_bytes: bytes, angle: int) -> bytes:
    """Undo a clockwise rotation of ``angle`` degrees (90, 180 or 270)."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        out = io.BytesIO()
        # PIL rotates counter-clockwise.
        image.rotate(angle, expand=True).save(out, format="PNG")
        return out.getvalue()


def rotate_box(
    box: tuple[float, float, float, float], angle: int
) -> tuple[float, float, float, float]:
    """Move a relative (x, y, width, height) box from the upright page onto the
    page rotated ``angle`` degrees clockwise (0, 90, 180 or 270)."""
    x, y, w, h = box
    if angle == 90:
        return 1 - y - h, x, h, w
    if angle == 180:
        return 1 - x - w, 1 - y - h, w, h
    if angle == 270:
        return y, 1 - x - w, h, w
    return box
