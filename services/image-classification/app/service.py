"""Image classification service: what does this image show, from a description?

Each label of a classification is described in words; the model (CLIP by
default) says which description each image matches best. Images come from the
bucket by key: plain images, or the parser's pages (their screenshots).
"""

from __future__ import annotations

import io
import logging
import uuid
from typing import Any

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from worker.core.services.base import BaseService, TaskStatus

from app.classifiers import ImageClassifier, get_classifier
from app.config import settings
from app.errors import ImageClassificationError
from app.schemas import (
    ClassificationTask,
    ImageClassificationInput,
    ImageClassificationOutput,
    ImageResult,
    InputImage,
    TaskResult,
)
from app.storage import Storage

logger = logging.getLogger("lisa.service.image_classification")


def to_result(task: ClassificationTask, probabilities: dict[str, float]) -> TaskResult:
    """Labels from probabilities: the best one, or all those above the threshold."""
    if task.multi_label:
        threshold = (
            settings.IMAGE_THRESHOLD if task.threshold is None else task.threshold
        )
        chosen = [
            (label, p)
            for label, p in sorted(probabilities.items(), key=lambda kv: -kv[1])
            if p >= threshold
        ]
    else:
        best = max(probabilities.items(), key=lambda kv: kv[1])
        chosen = [best]
    return TaskResult(
        name=task.name,
        multi_label=task.multi_label,
        labels=[label for label, _ in chosen],
        scores=dict(chosen),
        probabilities=probabilities,
    )


class ImageClassificationService(BaseService):
    name = "image-classification"
    version = "0.1.0"
    description = (
        "Zero-shot image classification (CLIP): each label is described in "
        "words, and every image gets the description it matches best."
    )
    tags = ["image", "classification", "zero-shot", "clip"]
    type = "analyser"
    queue = settings.CELERY_QUEUE
    input_schema = ImageClassificationInput.model_json_schema()
    output_schema = ImageClassificationOutput.model_json_schema()

    def __init__(
        self,
        *,
        classifier: ImageClassifier | None = None,
        storage: Storage | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._classifier = classifier
        self.storage = storage or Storage()

    @property
    def classifier(self) -> ImageClassifier:
        """Built on first use, so the model only loads when work arrives."""
        if self._classifier is None:
            self._classifier = get_classifier()
        return self._classifier

    def _load_image(self, key: str) -> Image.Image:
        data = self.storage.read(key)
        if len(data) > settings.MAX_IMAGE_MB * 1024 * 1024:
            raise ImageClassificationError(
                f"'{key}' exceeds the {settings.MAX_IMAGE_MB:g} MB limit."
            )
        try:
            return Image.open(io.BytesIO(data)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ImageClassificationError(f"'{key}' is not an image: {exc}") from exc

    def classify_image(
        self, item: InputImage, tasks: list[ClassificationTask]
    ) -> ImageResult:
        image = self._load_image(item.s3_key)
        return ImageResult(
            s3_key=item.s3_key,
            page_number=item.page_number,
            classifications=[
                to_result(task, self.classifier.classify(image, task)) for task in tasks
            ],
        )

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = ImageClassificationInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise ImageClassificationError(f"Invalid input: {exc}") from exc
            items = [*request.images, *request.pages]
            if not items:
                raise ImageClassificationError(
                    "No image provided (expected 'images', or 'pages' with an s3_key)."
                )
            if not request.classifications:
                raise ImageClassificationError(
                    "No classification provided (expected 'classifications')."
                )
            # Checked before reading anything.
            self.storage.require_configured()
            results: list[ImageResult] = []
            for index, item in enumerate(items):
                results.append(self.classify_image(item, request.classifications))
                self.update_task(
                    task_id, progress=round((index + 1) / len(items) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = ImageClassificationOutput(
            id=task_id or f"image-classification-{uuid.uuid4()}",
            model=self.classifier.name,
            images=results,
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
