"""Extractor backends: the only place that knows about a particular model.

An extractor returns every relation of a page text (any length) with the
character offsets of both ends. To use another model, add a class with the
``Extractor`` interface, register it in ``BACKENDS`` and set
``RELATION_BACKEND``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config import settings
from app.errors import RelationError
from app.schemas import RelationRule


@dataclass
class RawEndpoint:
    text: str
    start: int
    end: int
    score: float | None = None


@dataclass
class RawRelation:
    relation: str
    head: RawEndpoint
    tail: RawEndpoint


class Extractor(Protocol):
    @property
    def name(self) -> str:
        """Identifier of the model, reported in the output."""

    def extract(
        self, text: str, rules: list[RelationRule], threshold: float
    ) -> list[RawRelation]:
        """Relations of ``text`` for the given rules (``threshold``: default cutoff)."""


def _endpoint(item: Any) -> RawEndpoint | None:
    """A head / tail dict with a span, else None (it cannot be located)."""
    if not isinstance(item, dict) or "start" not in item:
        return None
    score = item.get("confidence")
    return RawEndpoint(
        text=item["text"],
        start=int(item["start"]),
        end=int(item["end"]),
        score=float(score) if score is not None else None,
    )


def parse_relations(raw: dict[str, Any]) -> list[RawRelation]:
    """Turn GLiNER2's ``{"relation_extraction": {name: [{head, tail}]}}``."""
    found = []
    for name, items in (raw.get("relation_extraction") or {}).items():
        for item in items:
            if not isinstance(item, dict):
                continue  # a bare (head, tail) pair has no span
            head, tail = _endpoint(item.get("head")), _endpoint(item.get("tail"))
            if head and tail:
                found.append(RawRelation(relation=name, head=head, tail=tail))
    return found


class Gliner2Extractor:
    """Zero-shot relation extraction with GLiNER2 / GLiNER2.5 (long context)."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.RELATION_MODEL
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
    def _relation_types(rules: list[RelationRule]) -> dict[str, Any]:
        """{name: {description, threshold?}}: the per-relation form of the schema."""
        types: dict[str, Any] = {}
        for rule in rules:
            config: dict[str, Any] = {"description": rule.description or rule.name}
            if rule.threshold is not None:
                config["threshold"] = rule.threshold
            types[rule.name] = config
        return types

    def extract(
        self, text: str, rules: list[RelationRule], threshold: float
    ) -> list[RawRelation]:
        model = self._get_model()
        schema = model.create_schema().relations(
            self._relation_types(rules), threshold=threshold
        )
        # extract_long reads the whole page, in overlapping word windows, and
        # returns global character offsets. Both ends of a relation must sit in
        # one window.
        raw = model.extract_long(
            text,
            schema,
            threshold=threshold,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            include_spans=True,
            include_confidence=True,
        )
        return parse_relations(raw)


BACKENDS: dict[str, type[Extractor]] = {"gliner2": Gliner2Extractor}


def get_extractor(backend: str | None = None) -> Extractor:
    key = backend or settings.RELATION_BACKEND
    try:
        return BACKENDS[key]()
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise RelationError(
            f"Unknown RELATION_BACKEND '{key}' (available: {known})."
        ) from None
