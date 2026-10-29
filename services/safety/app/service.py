"""Safety service: malicious prompts and PII spans, page by page, in one pass.

Input is the parser output (``pages[].content``, optionally ``words`` to get
boxes) plus optional overrides of what to check. For every page the service
returns the safety verdict per task (prompt safety, jailbreak, toxicity...)
and the PII entities with their character offsets and, when the page has
words, their boxes. The model behind it is a pluggable ``Guard``
(see ``app.guards``), the GLiNER2 guardrails + PII checkpoint by default.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import ValidationError
from worker.core.services.base import BaseService, TaskStatus

from app.boxes import boxes_for_span
from app.config import settings
from app.defaults import DEFAULT_PII_LABELS, DEFAULT_SAFETY_TASKS
from app.errors import SafetyError
from app.guards import Guard, RawResult, get_guard
from app.schemas import (
    Entity,
    InputPage,
    Label,
    LabelScore,
    PageResult,
    SafetyInput,
    SafetyOutput,
    SafetyTask,
    TaskResult,
)

logger = logging.getLogger("lisa.service.safety")


class SafetyService(BaseService):
    name = "safety"
    version = "0.1.0"
    description = (
        "Detects malicious prompts (prompt safety, jailbreak, toxicity) and PII "
        "spans with their boxes, page by page, in one pass."
    )
    tags = ["safety", "guardrails", "pii", "gliner2"]
    type = "guard"
    queue = settings.CELERY_QUEUE
    input_schema = SafetyInput.model_json_schema()
    output_schema = SafetyOutput.model_json_schema()

    def __init__(self, *, guard: Guard | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._guard = guard

    @property
    def guard(self) -> Guard:
        """Built on first use, so the model only loads when work arrives."""
        if self._guard is None:
            self._guard = get_guard()
        return self._guard

    def analyse_page(
        self, page: InputPage, pii_labels: list[Label], tasks: list[SafetyTask]
    ) -> PageResult:
        if not page.content.strip():
            return PageResult(page_number=page.page_number)
        raw = self.guard.analyse(page.content, pii_labels, tasks)
        return self._build_page(page, raw, pii_labels, tasks)

    def _build_page(
        self,
        page: InputPage,
        raw: RawResult,
        pii_labels: list[Label],
        tasks: list[SafetyTask],
    ) -> PageResult:
        asked = {lb.name for lb in pii_labels}
        entities = [
            Entity(
                label=e.label,
                text=e.text,
                start=e.start,
                end=e.end,
                score=e.score,
                model=self.guard.name,
                bboxes=[
                    box.model_copy(
                        update={
                            "label": e.label,
                            "score": e.score,
                            "model": self.guard.name,
                        }
                    )
                    for box in boxes_for_span(
                        page.words, e.start, e.end, content=page.content
                    )
                ],
            )
            # Only what was asked for, in reading order.
            for e in sorted(raw.entities, key=lambda e: (e.start, e.end))
            if e.label in asked
        ]
        safety = []
        for task in tasks:
            allowed = set(task.label_names)
            labels = [
                LabelScore(label=lb, score=score, flagged=lb not in task.ok_labels)
                for lb, score in raw.tasks.get(task.name, [])
                if lb in allowed
            ]
            safety.append(
                TaskResult(
                    name=task.name,
                    multi_label=task.multi_label,
                    labels=labels,
                    flagged=any(lb.flagged for lb in labels),
                )
            )
        return PageResult(
            page_number=page.page_number,
            unsafe=any(t.flagged for t in safety),
            has_pii=bool(entities),
            safety=safety,
            entities=entities,
        )

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = SafetyInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise SafetyError(f"Invalid input: {exc}") from exc
            if not request.pages:
                raise SafetyError("No page provided (expected 'pages').")
            pii_labels = (
                DEFAULT_PII_LABELS if request.pii_labels is None else request.pii_labels
            )
            tasks = (
                DEFAULT_SAFETY_TASKS
                if request.safety_tasks is None
                else request.safety_tasks
            )
            if not pii_labels and not tasks:
                raise SafetyError(
                    "Nothing to check: no PII labels and no safety tasks."
                )
            pages: list[PageResult] = []
            for index, page in enumerate(request.pages):
                pages.append(self.analyse_page(page, pii_labels, tasks))
                self.update_task(
                    task_id, progress=round((index + 1) / len(request.pages) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = SafetyOutput(
            id=task_id or f"safety-{uuid.uuid4()}",
            model=self.guard.name,
            unsafe=any(p.unsafe for p in pages),
            has_pii=any(p.has_pii for p in pages),
            pages=pages,
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
