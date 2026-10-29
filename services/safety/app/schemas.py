"""Input and output contracts of the safety service."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Label(BaseModel):
    """A label, optionally defined by a description."""

    name: str = Field(min_length=1)
    description: str | None = Field(
        default=None,
        description="What the label means: helps the model tell labels apart.",
    )


def _bare_strings_are_labels(value: Any) -> Any:
    if isinstance(value, list):
        return [{"name": v} if isinstance(v, str) else v for v in value]
    return value


class SafetyTask(BaseModel):
    """One safety classification run on every page (e.g. jailbreak detection)."""

    name: str = Field(min_length=1)
    labels: list[Label] = Field(min_length=1)
    multi_label: bool = False
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Minimum score in multi-label mode (default SAFETY_THRESHOLD).",
    )
    ok_labels: list[str] = Field(
        default_factory=list,
        description="Labels meaning 'nothing wrong' (e.g. safe, benign). Any other "
        "label makes the page unsafe.",
    )

    _labels = field_validator("labels", mode="before")(_bare_strings_are_labels)

    @model_validator(mode="after")
    def _check(self) -> SafetyTask:
        names = self.label_names
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate labels in task '{self.name}'.")
        unknown = set(self.ok_labels) - set(names)
        if unknown:
            raise ValueError(f"ok_labels not in labels of '{self.name}': {unknown}")
        return self

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]


class InputWord(BaseModel):
    """A parser word box (relative 0-1) with its offsets into the page content."""

    model_config = ConfigDict(extra="ignore")

    x: float
    y: float
    width: float
    height: float
    start: int
    end: int
    # Clockwise rotation (0, 90, 180 or 270) of the text on the page.
    angle: int = 0


class InputPage(BaseModel):
    # The parser's pages carry more fields (filename, s3_key...): ignored here.
    model_config = ConfigDict(extra="ignore")

    content: str = ""
    page_number: int | None = None
    # When given, detected entities also come back as boxes on the page.
    words: list[InputWord] = Field(default_factory=list)


class SafetyInput(BaseModel):
    """The parser output, plus optional overrides of what to check."""

    model_config = ConfigDict(extra="ignore")

    pages: list[InputPage] = Field(default_factory=list)
    pii_labels: list[Label] | None = Field(
        default=None,
        description="PII types to find. Omit for the defaults, [] to skip PII.",
    )
    safety_tasks: list[SafetyTask] | None = Field(
        default=None,
        description="Safety checks. Omit for the defaults, [] to skip safety.",
    )

    _pii = field_validator("pii_labels", mode="before")(_bare_strings_are_labels)

    @model_validator(mode="after")
    def _unique_task_names(self) -> SafetyInput:
        names = [t.name for t in self.safety_tasks or []]
        if len(set(names)) != len(names):
            raise ValueError("Safety task names must be unique.")
        return self


class Box(BaseModel):
    """A box relative to the page (0-1 fractions, origin top-left)."""

    x: float
    y: float
    width: float
    height: float
    # Clockwise rotation (0, 90, 180 or 270) of the text in the box.
    angle: int = 0
    # The part of the span this box covers: its text and offsets in the page
    # ``content`` (set when the page content is known).
    text: str | None = None
    start: int | None = None
    end: int | None = None
    # What the entity says, repeated on every box so each one stands alone.
    label: str | None = None
    score: float | None = None
    model: str | None = None


class Entity(BaseModel):
    label: str
    text: str
    # Character offsets into the page ``content``.
    start: int
    end: int
    score: float | None = None
    # Model that found the entity.
    model: str
    # One box per line the entity spans (needs ``words`` in the input page).
    bboxes: list[Box] = Field(default_factory=list)


class LabelScore(BaseModel):
    label: str
    score: float | None = None
    # True when the label is not one of the task's ``ok_labels``.
    flagged: bool


class TaskResult(BaseModel):
    name: str
    multi_label: bool
    labels: list[LabelScore] = Field(default_factory=list)
    flagged: bool = False


class PageResult(BaseModel):
    page_number: int | None = None
    # Any safety task flagged: the page looks malicious or harmful.
    unsafe: bool = False
    has_pii: bool = False
    safety: list[TaskResult] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)


class SafetyOutput(BaseModel):
    id: str
    model: str
    # Any page unsafe, resp. with PII.
    unsafe: bool = False
    has_pii: bool = False
    pages: list[PageResult] = Field(default_factory=list)
    error: str | None = None
