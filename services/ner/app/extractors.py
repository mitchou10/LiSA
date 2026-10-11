"""Extractor backends: the only place that knows about a particular model.

An extractor returns every entity of a page text (any length) with character
offsets and a score. To use another model, add a class with the ``Extractor``
interface, register it in ``BACKENDS`` and set ``NER_BACKEND``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config import settings
from app.errors import NerError
from app.schemas import EntityRule


@dataclass
class RawEntity:
    label: str
    text: str
    start: int
    end: int
    score: float


class Extractor(Protocol):
    @property
    def name(self) -> str:
        """Identifier of the model, reported in the output."""

    def extract(
        self, text: str, rules: list[EntityRule], threshold: float
    ) -> list[RawEntity]:
        """Entities of ``text`` for the given rules (``threshold``: default cutoff)."""


def parse_entities(raw: dict[str, Any]) -> list[RawEntity]:
    """Turn GLiNER2's ``{"entities": {label: [{text, confidence, start, end}]}}``."""
    found = []
    for label, items in (raw.get("entities") or {}).items():
        for item in items:
            if not isinstance(item, dict) or "start" not in item:
                continue  # no span: cannot be located, so cannot be redacted
            found.append(
                RawEntity(
                    label=label,
                    text=item["text"],
                    start=int(item["start"]),
                    end=int(item["end"]),
                    score=float(item.get("confidence", 0.0)),
                )
            )
    return found


class Gliner2Extractor:
    """Zero-shot NER with GLiNER2 / GLiNER2.5 (schema builder + long context)."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.NER_MODEL
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

    @staticmethod
    def _entity_types(rules: list[EntityRule]) -> dict[str, Any]:
        """{label: {description, threshold?}}: the per-label form of the schema."""
        types: dict[str, Any] = {}
        for rule in rules:
            config: dict[str, Any] = {"description": rule.description or rule.label}
            if rule.threshold is not None:
                config["threshold"] = rule.threshold
            types[rule.label] = config
        return types

    def extract(
        self, text: str, rules: list[EntityRule], threshold: float
    ) -> list[RawEntity]:
        model = self._get_model()
        schema = model.create_schema().entities(
            self._entity_types(rules), threshold=threshold
        )
        # extract_long reads the whole page, in overlapping word windows, and
        # returns global character offsets.
        raw = model.extract_long(
            text,
            schema,
            threshold=threshold,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            include_spans=True,
            include_confidence=True,
        )
        return parse_entities(raw)


BACKENDS: dict[str, type[Extractor]] = {"gliner2": Gliner2Extractor}


def get_extractor(backend: str | None = None) -> Extractor:
    key = backend or settings.NER_BACKEND
    try:
        return BACKENDS[key]()
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise NerError(f"Unknown NER_BACKEND '{key}' (available: {known}).") from None
