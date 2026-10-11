"""Input and output contracts of the image classification service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Label(BaseModel):
    """A candidate label; its description is what CLIP matches with the image."""

    name: str = Field(min_length=1)
    description: str | None = Field(
        default=None,
        description="What the image looks like, in English: 'a scanned invoice with "
        "a table of amounts'. Without it, the label name is used.",
    )


class ClassificationTask(BaseModel):
    """One classification to run on every image."""

    name: str = Field(min_length=1)
    labels: list[Label] = Field(min_length=2, description="At least two candidates.")
    multi_label: bool = Field(
        default=False,
        description="False: the best label. True: every label above the threshold.",
    )
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Multi-label only (default IMAGE_THRESHOLD).",
    )

    @field_validator("labels", mode="before")
    @classmethod
    def _bare_strings(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"name": v} if isinstance(v, str) else v for v in value]
        return value

    @model_validator(mode="after")
    def _unique_labels(self) -> ClassificationTask:
        if len(set(self.label_names)) != len(self.label_names):
            raise ValueError(f"Duplicate labels in classification '{self.name}'.")
        return self

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]


class InputImage(BaseModel):
    """An image in the bucket."""

    model_config = ConfigDict(extra="ignore")

    s3_key: str = Field(min_length=1, description="Key of the image in the bucket.")
    page_number: int | None = None


class ImageClassificationInput(BaseModel):
    """Images, plus what to classify them as.

    ``images`` are plain image keys; ``pages`` is the parser's output (every page
    with an ``s3_key`` is its screenshot): both are classified.
    """

    model_config = ConfigDict(extra="ignore")

    images: list[InputImage] = Field(default_factory=list)
    pages: list[InputImage] = Field(default_factory=list)
    classifications: list[ClassificationTask] = Field(default_factory=list)

    @field_validator("pages", mode="before")
    @classmethod
    def _pages_without_screenshot_are_skipped(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [p for p in value if isinstance(p, dict) and p.get("s3_key")]
        return value

    @model_validator(mode="after")
    def _unique_names(self) -> ImageClassificationInput:
        names = [c.name for c in self.classifications]
        if len(set(names)) != len(names):
            raise ValueError("Classification names must be unique.")
        return self


class TaskResult(BaseModel):
    name: str
    multi_label: bool
    # One label in single-label mode, those above the threshold in multi-label.
    labels: list[str] = Field(default_factory=list)
    # Probability of each returned label.
    scores: dict[str, float] = Field(default_factory=dict)
    # Probability of every candidate (they sum to 1): the full picture.
    probabilities: dict[str, float] = Field(default_factory=dict)


class ImageResult(BaseModel):
    s3_key: str
    page_number: int | None = None
    classifications: list[TaskResult] = Field(default_factory=list)


class ImageClassificationOutput(BaseModel):
    id: str
    # Model that produced the probabilities, e.g. "clip:openai/clip-vit-base-patch32".
    model: str
    images: list[ImageResult] = Field(default_factory=list)
    error: str | None = None
