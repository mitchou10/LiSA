"""Input and output contracts of the NER service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["low", "medium", "high"]
Action = Literal["allow", "redact", "block"]

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
ACTION_RANK = {"allow": 0, "redact": 1, "block": 2}


class EntityRule(BaseModel):
    """One entity type to look for, and what to do when it is found."""

    label: str = Field(min_length=1)
    description: str | None = Field(
        default=None,
        description="What the entity is, in plain words (with examples if useful): "
        "improves accuracy.",
    )
    category: str = "OTHER"
    severity: Severity = "medium"
    action: Action = "redact"
    enabled: bool = True
    threshold: float | None = Field(
        default=None, ge=0, le=1, description="Overrides the global threshold."
    )

    @field_validator("label")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("category")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper() or "OTHER"


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
    # When given, entities also come back as boxes on the page.
    words: list[InputWord] = Field(default_factory=list)


class NerInput(BaseModel):
    """The parser output, plus optional overrides of what to look for."""

    model_config = ConfigDict(extra="ignore")

    pages: list[InputPage] = Field(default_factory=list)
    entities: list[EntityRule] | None = Field(
        default=None,
        description="Entity types to find, on demand. Omit to use the active "
        "detection profile.",
    )
    threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("entities", mode="before")
    @classmethod
    def _bare_strings(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"label": v} if isinstance(v, str) else v for v in value]
        return value

    @model_validator(mode="after")
    def _unique_labels(self) -> NerInput:
        labels = [e.label.lower() for e in self.entities or []]
        if len(set(labels)) != len(labels):
            raise ValueError("Entity labels must be unique.")
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
    category: str | None = None
    score: float | None = None
    severity: Severity | None = None
    action: Action | None = None
    flagged: bool | None = None
    model: str | None = None


class Entity(BaseModel):
    id: str
    label: str
    category: str
    text: str
    # Character offsets into the page ``content``.
    start: int
    end: int
    score: float
    severity: Severity
    action: Action
    # False when the label's action is "allow" (found, but no action needed).
    flagged: bool
    # Model that found the entity.
    model: str
    # One box per line the entity spans (needs ``words`` in the input page).
    bboxes: list[Box] = Field(default_factory=list)


class PageResult(BaseModel):
    page_number: int | None = None
    flagged: bool = False
    severity: Severity | None = None
    action: Action = "allow"
    entities: list[Entity] = Field(default_factory=list)


class NerOutput(BaseModel):
    id: str
    model: str
    # Version of the detection profile used, when the profile drove the labels.
    profile_version: int | None = None
    flagged: bool = False
    severity: Severity | None = None
    action: Action = "allow"
    pages: list[PageResult] = Field(default_factory=list)
    error: str | None = None
