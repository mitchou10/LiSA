"""Input and output contracts of the classification service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Label(BaseModel):
    """A candidate label, optionally defined by a description."""

    name: str = Field(min_length=1)
    description: str | None = Field(
        default=None,
        description="What the label means: helps the model tell similar labels apart.",
    )


class ClassificationTask(BaseModel):
    """One classification to look for on every page."""

    name: str = Field(min_length=1, description="Key of the result, e.g. 'doc_type'.")
    labels: list[Label] = Field(
        min_length=1,
        description="Candidate labels. A bare string is a label without description.",
    )
    multi_label: bool = Field(
        default=False,
        description="False: exactly one label per page. True: every label that applies.",
    )
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Minimum score in multi-label mode (defaults to CLASSIFIER_THRESHOLD).",
    )

    @field_validator("labels", mode="before")
    @classmethod
    def _bare_strings_are_labels(cls, value: Any) -> Any:
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


class InputPage(BaseModel):
    # The parser's pages carry many more fields (boxes, s3_key...): ignored here.
    model_config = ConfigDict(extra="ignore")

    content: str = ""
    page_number: int | None = None


class ClassificationInput(BaseModel):
    """The parser output, plus what to look for."""

    model_config = ConfigDict(extra="ignore")

    pages: list[InputPage] = Field(default_factory=list)
    classifications: list[ClassificationTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names(self) -> ClassificationInput:
        names = [c.name for c in self.classifications]
        if len(set(names)) != len(names):
            raise ValueError("Classification names must be unique.")
        return self


class TaskResult(BaseModel):
    name: str
    multi_label: bool
    # Always a list: one element in single-label mode, empty if nothing applies.
    labels: list[str] = Field(default_factory=list)
    # Probability of each returned label (when the model gives one).
    scores: dict[str, float] = Field(default_factory=dict)


class PageResult(BaseModel):
    page_number: int | None = None
    classifications: list[TaskResult] = Field(default_factory=list)


class ClassificationOutput(BaseModel):
    id: str
    # Model that produced the labels, e.g. "gliner2:fastino/gliner2.5-multi-v1".
    model: str
    pages: list[PageResult] = Field(default_factory=list)
    error: str | None = None
