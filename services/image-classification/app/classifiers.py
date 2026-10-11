"""Classifier backends: the only place that knows about a particular model.

A backend gives, for one image and one classification, the probability of each
candidate label. Turning probabilities into labels (best one, or all above a
threshold) is the service's job, so any model fits. To use another one, add a
class with the ``ImageClassifier`` interface, register it in ``BACKENDS`` and
set ``IMAGE_BACKEND``.
"""

from __future__ import annotations

from typing import Any, Protocol

from PIL import Image

from app.config import settings
from app.errors import ImageClassificationError
from app.schemas import ClassificationTask


class ImageClassifier(Protocol):
    @property
    def name(self) -> str:
        """Identifier of the model, reported in the output."""

    def classify(
        self, image: Image.Image, task: ClassificationTask
    ) -> dict[str, float]:
        """Probability of every label of ``task`` for ``image`` (summing to 1)."""


def _embedding(output: Any) -> Any:
    """The embedding tensor: older transformers return it, newer ones wrap it."""
    return output if hasattr(output, "norm") else output.pooler_output


class ClipClassifier:
    """Zero-shot classification with CLIP: the image is matched with a text
    describing each label, and the matches are turned into probabilities."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.IMAGE_MODEL
        self._model: Any = None
        self._processor: Any = None
        # Text embeddings per list of prompts: the labels rarely change while
        # many images go through them.
        self._text_cache: dict[tuple[str, ...], Any] = {}

    @property
    def name(self) -> str:
        return f"clip:{self._model_name}"

    def _load(self) -> tuple[Any, Any]:
        # Imported and loaded on first use: torch is heavy and tests mock it.
        if self._model is None:
            from transformers import CLIPModel, CLIPProcessor

            self._model = CLIPModel.from_pretrained(self._model_name).eval()
            self._processor = CLIPProcessor.from_pretrained(self._model_name)
        return self._model, self._processor

    @staticmethod
    def prompts(task: ClassificationTask) -> list[str]:
        """The text matched with the image for each label."""
        return [
            label.description or settings.IMAGE_PROMPT_TEMPLATE.format(label=label.name)
            for label in task.labels
        ]

    def _text_features(self, prompts: tuple[str, ...]) -> Any:
        import torch

        if prompts not in self._text_cache:
            model, processor = self._load()
            tokens = processor(
                text=list(prompts), return_tensors="pt", padding=True, truncation=True
            )
            with torch.no_grad():
                features = _embedding(model.get_text_features(**tokens))
            self._text_cache[prompts] = features / features.norm(dim=-1, keepdim=True)
        return self._text_cache[prompts]

    def classify(
        self, image: Image.Image, task: ClassificationTask
    ) -> dict[str, float]:
        import torch

        text = self._text_features(tuple(self.prompts(task)))
        model, processor = self._load()
        with torch.no_grad():
            pixels = processor(images=image, return_tensors="pt")
            features = _embedding(model.get_image_features(**pixels))
            features = features / features.norm(dim=-1, keepdim=True)
            logits = model.logit_scale.exp() * features @ text.T
            probabilities = logits.softmax(dim=-1)[0].tolist()
        return dict(zip(task.label_names, probabilities, strict=True))


BACKENDS: dict[str, type[ImageClassifier]] = {"clip": ClipClassifier}


def get_classifier(backend: str | None = None) -> ImageClassifier:
    key = backend or settings.IMAGE_BACKEND
    try:
        return BACKENDS[key]()
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise ImageClassificationError(
            f"Unknown IMAGE_BACKEND '{key}' (available: {known})."
        ) from None
