"""Relation extraction service: who/what is linked to whom, page by page.

Input is the parser output (``pages[].content``, optionally ``words`` to get
boxes) plus optionally the relation types to look for. For every page the
service returns the relations with, for both ends, the character offsets and,
when the page has words, the relative boxes. The model behind it is a pluggable
``Extractor`` (see ``app.extractors``), GLiNER2.5 by default, which reads pages
of any length in overlapping windows.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import ValidationError
from worker.core.services.base import BaseService, TaskStatus

from app.boxes import boxes_for_span
from app.config import settings
from app.defaults import DEFAULT_RELATIONS
from app.errors import RelationError
from app.extractors import Extractor, RawEndpoint, get_extractor
from app.schemas import (
    Endpoint,
    InputPage,
    PageResult,
    Relation,
    RelationInput,
    RelationOutput,
    RelationRule,
)

logger = logging.getLogger("lisa.service.relation")


class RelationService(BaseService):
    name = "relation"
    version = "0.1.0"
    description = (
        "Zero-shot relation extraction (GLiNER2): relations between entities per "
        "page, both ends with character spans and relative boxes."
    )
    tags = ["relation", "relations", "gliner2", "multilingual"]
    type = "analyser"
    queue = settings.CELERY_QUEUE
    input_schema = RelationInput.model_json_schema()
    output_schema = RelationOutput.model_json_schema()

    def __init__(self, *, extractor: Extractor | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._extractor = extractor

    @property
    def extractor(self) -> Extractor:
        """Built on first use, so the model only loads when work arrives."""
        if self._extractor is None:
            self._extractor = get_extractor()
        return self._extractor

    @staticmethod
    def _endpoint(page: InputPage, raw: RawEndpoint) -> Endpoint:
        return Endpoint(
            text=raw.text,
            start=raw.start,
            end=raw.end,
            score=raw.score,
            bboxes=boxes_for_span(page.words, raw.start, raw.end),
        )

    def analyse_page(
        self, page: InputPage, rules: list[RelationRule], threshold: float
    ) -> PageResult:
        if not page.content.strip() or not rules:
            return PageResult(page_number=page.page_number)
        asked = {r.name: r for r in rules}
        raw = self.extractor.extract(page.content, rules, threshold)
        relations: list[Relation] = []
        # In reading order of the head; only relation types that were asked for.
        for rel in sorted(raw, key=lambda r: (r.head.start, r.tail.start)):
            rule = asked.get(rel.relation)
            if rule is None:
                continue
            scores = [s for s in (rel.head.score, rel.tail.score) if s is not None]
            score = min(scores) if scores else None
            cutoff = threshold if rule.threshold is None else rule.threshold
            if score is not None and score < cutoff:
                continue
            relations.append(
                Relation(
                    id=f"r{len(relations)}",
                    relation=rel.relation,
                    head=self._endpoint(page, rel.head),
                    tail=self._endpoint(page, rel.tail),
                    score=score,
                    model=self.extractor.name,
                )
            )
        return PageResult(page_number=page.page_number, relations=relations)

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = RelationInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise RelationError(f"Invalid input: {exc}") from exc
            if not request.pages:
                raise RelationError("No page provided (expected 'pages').")
            rules = (
                DEFAULT_RELATIONS if request.relations is None else request.relations
            )
            if not rules:
                raise RelationError("Nothing to look for: 'relations' is empty.")
            threshold = (
                settings.RELATION_THRESHOLD
                if request.threshold is None
                else request.threshold
            )
            pages: list[PageResult] = []
            for index, page in enumerate(request.pages):
                pages.append(self.analyse_page(page, rules, threshold))
                self.update_task(
                    task_id, progress=round((index + 1) / len(request.pages) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        result = RelationOutput(
            id=task_id or f"relation-{uuid.uuid4()}",
            model=self.extractor.name,
            pages=pages,
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
