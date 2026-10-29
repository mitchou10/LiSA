"""NER service: sensitive entities, page by page, with spans and boxes.

Input is the parser output (``pages[].content``, optionally ``words`` to get
boxes). What to look for comes from the live detection profile edited in LiSA
(labels, categories, severities, actions), or from ``entities`` in the input
for an on-demand run. For every page the service returns the entities with
their character offsets and, when the page has words, their relative boxes.
The model behind it is a pluggable ``Extractor`` (see ``app.extractors``),
GLiNER2.5 by default, which reads pages of any length in overlapping windows.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import ValidationError
from worker.core.client.detection_profiles import DetectionProfileClient
from worker.core.services.base import BaseService, TaskStatus

from app.boxes import boxes_for_span
from app.config import settings
from app.defaults import DEFAULT_ENTITIES
from app.errors import NerError
from app.extractors import Extractor, get_extractor
from app.profile import Profile, ProfileProvider
from app.schemas import (
    ACTION_RANK,
    SEVERITY_RANK,
    Entity,
    EntityRule,
    InputPage,
    NerInput,
    NerOutput,
    PageResult,
)

logger = logging.getLogger("lisa.service.ner")


def _aggregate(entities: list[Entity]) -> dict[str, Any]:
    """Page / document verdict from the flagged entities."""
    flagged = [e for e in entities if e.flagged]
    return {
        "flagged": bool(flagged),
        "severity": max((e.severity for e in flagged), key=SEVERITY_RANK.__getitem__)
        if flagged
        else None,
        "action": max((e.action for e in flagged), key=ACTION_RANK.__getitem__)
        if flagged
        else "allow",
    }


class NerService(BaseService):
    name = "ner"
    version = "0.1.0"
    description = (
        "Zero-shot named entity recognition (GLiNER2): sensitive entities per "
        "page with character spans and relative boxes, labels from the live "
        "detection profile or given on demand."
    )
    tags = ["ner", "entities", "pii", "gliner2", "multilingual"]
    type = "analyser"
    queue = settings.CELERY_QUEUE
    input_schema = NerInput.model_json_schema()
    output_schema = NerOutput.model_json_schema()

    def __init__(
        self,
        *,
        extractor: Extractor | None = None,
        profile_provider: ProfileProvider | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._extractor = extractor
        self._profiles = profile_provider or self._build_profile_provider()

    @property
    def extractor(self) -> Extractor:
        """Built on first use, so the model only loads when work arrives."""
        if self._extractor is None:
            self._extractor = get_extractor()
        return self._extractor

    # -- detection profile -------------------------------------------------
    def _build_profile_provider(self) -> ProfileProvider:
        """Live profile from the backend when enabled, else the defaults."""
        fetch = None
        if settings.PROFILE_ENABLED:
            client = DetectionProfileClient()
            fetch = lambda: client.get_active_config(settings.PROFILE_KEY)
        return ProfileProvider(
            service_key=settings.PROFILE_KEY,
            fallback=self._default_profile,
            fetch=fetch,
            redis_url=settings.REDIS_URL if fetch else None,
            channel=settings.PROFILE_CHANNEL,
            refresh_seconds=settings.PROFILE_REFRESH_SECONDS,
        )

    @staticmethod
    def _default_profile() -> Profile:
        return {
            "version": None,
            "threshold": settings.NER_THRESHOLD,
            "entities": [rule.model_dump() for rule in DEFAULT_ENTITIES],
        }

    def _resolve_rules(
        self, request: NerInput
    ) -> tuple[list[EntityRule], float, int | None]:
        """Rules, default threshold and profile version for this task."""
        if request.entities is not None:
            threshold = (
                settings.NER_THRESHOLD
                if request.threshold is None
                else request.threshold
            )
            return request.entities, threshold, None
        profile = self._profiles.get()
        threshold = (
            float(profile["threshold"])
            if request.threshold is None
            else request.threshold
        )
        rules = [EntityRule.model_validate(e) for e in profile["entities"]]
        return rules, threshold, profile.get("version")

    # -- page scanning -----------------------------------------------------
    def analyse_page(
        self, page: InputPage, rules: list[EntityRule], threshold: float
    ) -> PageResult:
        active = {r.label: r for r in rules if r.enabled}
        if not page.content.strip() or not active:
            return PageResult(page_number=page.page_number)
        raw = self.extractor.extract(page.content, list(active.values()), threshold)
        entities: list[Entity] = []
        # Reading order; only labels that were asked for.
        for ent in sorted(raw, key=lambda e: (e.start, e.end)):
            rule = active.get(ent.label)
            if rule is None:
                continue
            cutoff = threshold if rule.threshold is None else rule.threshold
            if ent.score < cutoff:
                continue
            boxes = boxes_for_span(page.words, ent.start, ent.end, content=page.content)
            entities.append(
                Entity(
                    id=f"e{len(entities)}",
                    label=ent.label,
                    category=rule.category,
                    text=ent.text,
                    start=ent.start,
                    end=ent.end,
                    score=ent.score,
                    severity=rule.severity,
                    action=rule.action,
                    flagged=rule.action != "allow",
                    model=self.extractor.name,
                    bboxes=[
                        box.model_copy(
                            update={
                                "label": ent.label,
                                "category": rule.category,
                                "score": ent.score,
                                "severity": rule.severity,
                                "action": rule.action,
                                "flagged": rule.action != "allow",
                                "model": self.extractor.name,
                            }
                        )
                        for box in boxes
                    ],
                )
            )
        return PageResult(
            page_number=page.page_number, entities=entities, **_aggregate(entities)
        )

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)
        try:
            try:
                request = NerInput.model_validate(input_data or {})
            except ValidationError as exc:
                raise NerError(f"Invalid input: {exc}") from exc
            if not request.pages:
                raise NerError("No page provided (expected 'pages').")
            rules, threshold, version = self._resolve_rules(request)
            pages: list[PageResult] = []
            for index, page in enumerate(request.pages):
                pages.append(self.analyse_page(page, rules, threshold))
                self.update_task(
                    task_id, progress=round((index + 1) / len(request.pages) * 100)
                )
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        all_entities = [e for p in pages for e in p.entities]
        result = NerOutput(
            id=task_id or f"ner-{uuid.uuid4()}",
            model=self.extractor.name,
            profile_version=version,
            pages=pages,
            **_aggregate(all_entities),
        ).model_dump()
        self.update_task(
            task_id, status=TaskStatus.SUCCESS, progress=100, output_data=result
        )
        return result
