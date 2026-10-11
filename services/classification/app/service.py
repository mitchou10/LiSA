"""Classification service: label every parsed page against a list of tasks.

Input is the parser's output (``pages[].content``) plus ``classifications``:
what to look for, each task single- or multi-label. For every page the service
returns, per task, the labels that apply. The model behind it is a pluggable
``Classifier`` (see ``app.classifiers``), GLiNER2 by default.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import ValidationError
from worker.core.services.base import BaseService, TaskStatus

from app.classifiers import Classifier, get_classifier
from app.config import settings
from app.errors import ClassificationError
from app.schemas import (
    ClassificationInput,
    ClassificationOutput,
    ClassificationTask,
    InputPage,
    PageResult,
    TaskResult,
)

logger = logging.getLogger("lisa.service.classification")


class ClassificationService(BaseService):
    name = "classification"
    version = "0.1.0"
    description = (
        "Classifies each page of a parsed document against a list of "
        "classifications (single or multi-label) with a zero-shot model."
    )
    tags = ["classification", "zero-shot", "gliner2"]
    type = "analyser"
    queue = settings.CELERY_QUEUE
    input_schema = ClassificationInput.model_json_schema()
    output_schema = ClassificationOutput.model_json_schema()

    def __init__(self, *, classifier: Classifier | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._classifier = classifier

    @property
    def classifier(self) -> Classifier:
        """Built on first use, so the model only loads when work arrives."""
        if self._classifier is None:
            self._classifier = get_classifier()
        return self._classifier

    def _classify_task(
        self, text: str, task: ClassificationTask
    ) -> list[tuple[str, float | None]]:
        # Whatever the model returns, only the labels asked for are kept.
        found = self.classifier.classify(text, task)
        return [(label, score) for label, score in found if label in task.label_names]

    def classify_page(
        self, page: InputPage, tasks: list[ClassificationTask]
    ) -> PageResult:
        results = []
        for task in tasks:
            found = (
                self._classify_task(page.content, task) if page.content.strip() else []
            )
            results.append(
                TaskResult(
                    name=task.name,
                    multi_label=task.multi_label,
                    labels=[label for label, _ in found],
                    scores={
                        label: score for label, score in found if score is not None
                    },
                )
            )
        return PageResult(page_number=page.page_number, classifications=results)

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = ClassificationInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise ClassificationError(f"Invalid input: {exc}") from exc
            if not request.pages:
                raise ClassificationError("No page provided (expected 'pages').")
            if not request.classifications:
                raise ClassificationError(
                    "No classification provided (expected 'classifications')."
                )
            pages: list[PageResult] = []
            for index, page in enumerate(request.pages):
                pages.append(self.classify_page(page, request.classifications))
                self.update_task(
                    task_id, progress=round((index + 1) / len(request.pages) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = ClassificationOutput(
            id=task_id or f"classification-{uuid.uuid4()}",
            model=self.classifier.name,
            pages=pages,
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
