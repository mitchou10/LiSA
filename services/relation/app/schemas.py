"""Input and output contracts of the relation extraction service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RelationRule(BaseModel):
    """One relation type to look for."""

    name: str = Field(min_length=1, description="Relation name, e.g. 'works_for'.")
    description: str | None = Field(
        default=None,
        description="What the relation means and which way it goes (head -> tail), "
        "e.g. 'Employment: the head is a person, the tail the organization'. "
        "Improves accuracy.",
    )
    threshold: float | None = Field(
        default=None, ge=0, le=1, description="Overrides the global threshold."
    )

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class InputWord(BaseModel):
    """A parser word box (relative 0-1) with its offsets into the page content."""

    model_config = ConfigDict(extra="ignore")

    x: float
    y: float
    width: float
    height: float
    start: int
    end: int


class InputPage(BaseModel):
    # The parser's pages carry more fields (filename, s3_key...): ignored here.
    model_config = ConfigDict(extra="ignore")

    content: str = ""
    page_number: int | None = None
    # When given, both ends of a relation also come back as boxes on the page.
    words: list[InputWord] = Field(default_factory=list)


class RelationInput(BaseModel):
    """The parser output, plus optional overrides of what to look for."""

    model_config = ConfigDict(extra="ignore")

    pages: list[InputPage] = Field(default_factory=list)
    relations: list[RelationRule] | None = Field(
        default=None,
        description="Relation types to find. Omit for the defaults.",
    )
    threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("relations", mode="before")
    @classmethod
    def _bare_strings(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [{"name": v} if isinstance(v, str) else v for v in value]
        return value

    @model_validator(mode="after")
    def _unique_names(self) -> RelationInput:
        names = [r.name.lower() for r in self.relations or []]
        if len(set(names)) != len(names):
            raise ValueError("Relation names must be unique.")
        return self


class Box(BaseModel):
    """A box relative to the page (0-1 fractions, origin top-left)."""

    x: float
    y: float
    width: float
    height: float


class Endpoint(BaseModel):
    """One end of a relation: a span of the page content."""

    text: str
    # Character offsets into the page ``content``.
    start: int
    end: int
    score: float | None = None
    # One box per line the span covers (needs ``words`` in the input page).
    bboxes: list[Box] = Field(default_factory=list)


class Relation(BaseModel):
    id: str
    relation: str
    head: Endpoint
    tail: Endpoint
    # Lowest of the two endpoint scores: the relation is as sure as its weakest end.
    score: float | None = None
    # Model that found the relation.
    model: str


class PageResult(BaseModel):
    page_number: int | None = None
    relations: list[Relation] = Field(default_factory=list)


class RelationOutput(BaseModel):
    id: str
    model: str
    pages: list[PageResult] = Field(default_factory=list)
    error: str | None = None
