"""Classifier backends: the only place that knows about a particular model.

A backend receives a whole page text and is responsible for long inputs (the
GLiNER2 one scans the page in overlapping windows). To use another model, add a
class with the ``Classifier`` interface, register it in ``BACKENDS`` and set
``CLASSIFIER_BACKEND`` (and ``CLASSIFIER_MODEL``).
"""

from __future__ import annotations

from typing import Any, Protocol

from app.config import settings
from app.errors import ClassificationError
from app.schemas import ClassificationTask


class Classifier(Protocol):
    """Anything able to label a text against a classification task."""

    @property
    def name(self) -> str:
        """Identifier of the model, reported in the output."""

    def classify(
        self, text: str, task: ClassificationTask
    ) -> list[tuple[str, float | None]]:
        """``(label, probability)`` of ``task`` that apply to ``text``.

        One pair in single-label mode, several if multi. The probability is
        ``None`` when the model does not give one.
        """


def parse_labels(result: Any) -> list[tuple[str, float | None]]:
    """GLiNER2's answer for one task as ``(label, confidence)`` pairs.

    With ``include_confidence`` it is ``{"label", "confidence"}`` (or a list of
    them); without, a label (or a list of labels).
    """
    if result is None:
        return []
    pairs = []
    for item in result if isinstance(result, list) else [result]:
        label = item.get("label") if isinstance(item, dict) else item
        if not isinstance(label, str):
            continue
        confidence = item.get("confidence") if isinstance(item, dict) else None
        pairs.append((label, float(confidence) if confidence is not None else None))
    return pairs


class Gliner2Classifier:
    """Zero-shot classification with GLiNER2 / GLiNER2.5.

    Uses ``classify_text_long`` so a page of any length is read in full, in
    overlapping word windows, instead of being truncated to the model's window.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.CLASSIFIER_MODEL
        self._model: Any = None

    @property
    def name(self) -> str:
        return f"gliner2:{self._model_name}"

    def _get_model(self) -> Any:
        # Imported and loaded on first use: torch is heavy and tests mock it.
        if self._model is None:
            # AutoExtractor picks the right architecture: span checkpoints
            # (gliner2-*) and boundary checkpoints (gliner2.5-*) alike.
            from gliner2 import AutoExtractor

            self._model = AutoExtractor.from_pretrained(self._model_name)
        return self._model

    def classify(
        self, text: str, task: ClassificationTask
    ) -> list[tuple[str, float | None]]:
        # GLiNER2 takes the labels as a list, or as {label: description}.
        labels: list[str] | dict[str, str] = (
            {lb.name: lb.description or lb.name for lb in task.labels}
            if any(lb.description for lb in task.labels)
            else task.label_names
        )
        if task.multi_label:
            threshold = (
                settings.CLASSIFIER_THRESHOLD
                if task.threshold is None
                else task.threshold
            )
            schema: dict[str, Any] = {
                task.name: {
                    "labels": labels,
                    "multi_label": True,
                    "cls_threshold": threshold,
                }
            }
        else:
            schema = {task.name: labels}
        result = (
            self._get_model()
            .classify_text_long(
                text,
                schema,
                chunk_size=settings.CLASSIFIER_CHUNK_SIZE,
                chunk_overlap=settings.CLASSIFIER_CHUNK_OVERLAP,
                include_confidence=True,
            )
            .get(task.name)
        )
        return parse_labels(result)


BACKENDS: dict[str, type[Classifier]] = {"gliner2": Gliner2Classifier}


def get_classifier(backend: str | None = None) -> Classifier:
    key = backend or settings.CLASSIFIER_BACKEND
    try:
        return BACKENDS[key]()
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise ClassificationError(
            f"Unknown CLASSIFIER_BACKEND '{key}' (available: {known})."
        ) from None
