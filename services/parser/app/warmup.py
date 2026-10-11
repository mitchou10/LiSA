"""Download the Tesseract language data at image build time.

LiteParse fetches ``<lang>.traineddata`` on first OCR use; running one OCR pass
while building the image bakes the data in, so workers start offline.
"""

from __future__ import annotations

import struct
import zlib

from liteparse import LiteParse

from app.config import settings


def _png(width: int = 64, height: int = 64) -> bytes:
    """A tiny white RGB PNG, built with the standard library only."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    LiteParse(ocr_language=settings.OCR_LANGUAGE, quiet=True).parse(_png())
    print(f"Tesseract data ready for '{settings.OCR_LANGUAGE}'.")
