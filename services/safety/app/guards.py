"""Guard backends: the only place that knows about a particular model.

A guard checks one page text for PII spans and safety classes in a single call
and returns plain data. To use another model, add a class with the ``Guard``
interface, register it in ``BACKENDS`` and set ``SAFETY_BACKEND``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings
from app.errors import SafetyError
from app.schemas import Label, SafetyTask


@dataclass
class RawEntity:
    label: str
    text: str
    start: int
    end: int
    score: float | None = None


@dataclass
class RawResult:
    entities: list[RawEntity] = field(default_factory=list)
    # Task name -> [(label, score)]: one pair in single-label mode.
    tasks: dict[str, list[tuple[str, float | None]]] = field(default_factory=dict)


class Guard(Protocol):
    @property
    def name(self) -> str:
        """Identifier of the model, reported in the output."""

    def analyse(
        self, text: str, pii_labels: list[Label], tasks: list[SafetyTask]
    ) -> RawResult:
        """PII spans and safety labels of ``text`` (any length)."""


def _labels_arg(labels: list[Label]) -> list[str] | dict[str, str]:
    """GLiNER2 takes labels as a list, or as {label: description}."""
    if any(lb.description for lb in labels):
        return {lb.name: lb.description or lb.name for lb in labels}
    return [lb.name for lb in labels]


def _score(item: Any) -> float | None:
    value = item.get("confidence") if isinstance(item, dict) else None
    return float(value) if value is not None else None


def _parse_task(value: Any) -> list[tuple[str, float | None]]:
    """Normalise a classification result: str, dict or a list of either."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    pairs = []
    for item in items:
        label = item.get("label") if isinstance(item, dict) else item
        if isinstance(label, str):
            pairs.append((label, _score(item)))
    return pairs


def parse_result(raw: dict[str, Any], tasks: list[SafetyTask]) -> RawResult:
    """Turn GLiNER2's ``extract`` output into a ``RawResult``."""
    entities = []
    for label, items in (raw.get("entities") or {}).items():
        for item in items:
            if not isinstance(item, dict) or "start" not in item:
                continue  # no span: cannot be located, so cannot be redacted
            entities.append(
                RawEntity(
                    label=label,
                    text=item["text"],
                    start=int(item["start"]),
                    end=int(item["end"]),
                    score=_score(item),
                )
            )
    return RawResult(
        entities=entities,
        tasks={t.name: _parse_task(raw.get(t.name)) for t in tasks},
    )


class Gliner2Guard:
    """Guardrails + PII in one pass with a GLiNER2 checkpoint."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.SAFETY_MODEL
        self._model: Any = None

    @property
    def name(self) -> str:
        return f"gliner2:{self._model_name}"

    def _get_model(self) -> Any:
        # Imported and loaded on first use: torch is heavy and tests mock it.
        if self._model is None:
            from gliner2 import AutoExtractor

            self._model = AutoExtractor.from_pretrained(self._model_name)
        return self._model

    def analyse(
        self, text: str, pii_labels: list[Label], tasks: list[SafetyTask]
    ) -> RawResult:
        model = self._get_model()
        schema = model.create_schema()
        if pii_labels:
            schema.entities(
                {lb.name: lb.description or lb.name for lb in pii_labels},
                threshold=settings.PII_THRESHOLD,
            )
        for task in tasks:
            threshold = (
                settings.SAFETY_THRESHOLD if task.threshold is None else task.threshold
            )
            schema.classification(
                task.name,
                _labels_arg(task.labels),
                multi_label=task.multi_label,
                cls_threshold=threshold,
            )
        # extract_long reads the whole page, in overlapping word windows.
        raw = model.extract_long(
            text,
            schema,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            include_spans=True,
            include_confidence=True,
        )
        return parse_result(raw, tasks)


BACKENDS: dict[str, type[Guard]] = {"gliner2": Gliner2Guard}


def get_guard(backend: str | None = None) -> Guard:
    key = backend or settings.SAFETY_BACKEND
    try:
        return BACKENDS[key]()
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise SafetyError(
            f"Unknown SAFETY_BACKEND '{key}' (available: {known})."
        ) from None
