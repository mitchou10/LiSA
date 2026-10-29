"""PaddleOCR engine: page orientation and OCR of the pages without a text layer.

The models are the official ONNX exports of PaddlePaddle, run by ONNX Runtime
through PaddleOCR's own pre and post-processing (PaddlePaddle itself is not
installed). They are loaded from ``PADDLE_MODELS_DIR`` on first use, in the
worker process, so nothing is downloaded when a task runs.
"""

from __future__ import annotations

import io
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.errors import ParserError

OCR_MODEL = "paddleocr"
# Clockwise rotation, in degrees, of a page that is not upright.
ANGLES = (0, 90, 180, 270)


@dataclass
class OcrItem:
    """One OCR text line, in the same shape as a LiteParse ``TextItem``."""

    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float | None = None
    words: list[Any] = field(default_factory=list)


def _model_dir(name: str) -> str:
    folder = Path(settings.PADDLE_MODELS_DIR) / name
    if not (folder / "inference.onnx").is_file():
        raise ParserError(f"PaddleOCR model not found in {folder}.")
    return str(folder)


def _engine_config() -> dict[str, Any]:
    return {"intra_op_num_threads": settings.PADDLE_THREADS}


def _make_ocr() -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_detection_model_dir=_model_dir(settings.PADDLE_DET_MODEL),
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        text_recognition_model_dir=_model_dir(settings.PADDLE_REC_MODEL),
        # The orientation is handled once per page by the classifier below.
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="onnxruntime",
        engine_config=_engine_config(),
    )


def _make_orientation() -> Any:
    from paddleocr import DocImgOrientationClassification

    return DocImgOrientationClassification(
        model_name="PP-LCNet_x1_0_doc_ori",
        model_dir=_model_dir(settings.PADDLE_ORIENTATION_MODEL),
        engine="onnxruntime",
        engine_config=_engine_config(),
    )


def _array(image_bytes: bytes) -> Any:
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as image:
        return np.asarray(image.convert("RGB"))


class PaddleEngine:
    """Loads the models on first use and reads pages. The factories are how a
    test puts fakes in their place."""

    def __init__(
        self,
        ocr_factory: Callable[[], Any] = _make_ocr,
        orientation_factory: Callable[[], Any] = _make_orientation,
    ) -> None:
        self._ocr_factory = ocr_factory
        self._orientation_factory = orientation_factory
        self._ocr: Any = None
        self._orientation: Any = None
        self._lock = threading.Lock()

    def _models(self) -> tuple[Any, Any]:
        with self._lock:
            if self._ocr is None:
                self._ocr = self._ocr_factory()
            if self._orientation is None and settings.DETECT_ORIENTATION:
                self._orientation = self._orientation_factory()
        return self._ocr, self._orientation

    def orientation(self, image_bytes: bytes) -> int:
        """Clockwise degrees (0, 90, 180 or 270) by which the page is rotated.

        0 when detection is off, or when the classifier is not confident
        enough to turn a page that might well be upright.
        """
        if not settings.DETECT_ORIENTATION:
            return 0
        _, classifier = self._models()
        result = classifier.predict(_array(image_bytes))[0]
        labels, scores = result.get("label_names"), result.get("scores")
        if not labels:
            return 0
        angle = int(labels[0])
        score = float(scores[0]) if scores is not None and len(scores) else 1.0
        if angle not in ANGLES or score < settings.ORIENTATION_MIN_SCORE:
            return 0
        return angle

    def read(self, image_bytes: bytes) -> tuple[list[OcrItem], tuple[int, int]]:
        """OCR lines of an upright page image, in pixels, and the image size
        (width, height)."""
        ocr, _ = self._models()
        image = _array(image_bytes)
        height, width = image.shape[:2]
        result = ocr.predict(image)[0]
        texts = result.get("rec_texts") or []
        scores = result.get("rec_scores") or []
        boxes = result.get("rec_boxes")
        items: list[OcrItem] = []
        for i, text in enumerate(texts):
            if not str(text).strip() or boxes is None or i >= len(boxes):
                continue
            x0, y0, x1, y1 = (float(v) for v in boxes[i][:4])
            items.append(
                OcrItem(
                    text=str(text),
                    x=x0,
                    y=y0,
                    width=x1 - x0,
                    height=y1 - y0,
                    confidence=float(scores[i]) if i < len(scores) else None,
                )
            )
        return items, (width, height)
