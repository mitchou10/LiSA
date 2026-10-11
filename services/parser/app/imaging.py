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
