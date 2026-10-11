"""Run a project's analyses on a text or on files."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TaskStatus


class RunCreate(BaseModel):
    """What to analyse, and which of the project's definitions to apply.

    Give a ``text`` or ``file_ids`` (uploaded with ``POST /files``). For each
    kind of definition, omit the list to apply every enabled one, send ``[]`` to
    skip that kind, or list the ids to apply exactly those.
    """

    text: str | None = None
    file_ids: list[UUID] = Field(default_factory=list)
    # Files only: blur the page screenshots (default: the parser's setting).
    blur_screenshots: bool | None = None

    classification_ids: list[UUID] | None = None
    entity_ids: list[UUID] | None = None
    relation_ids: list[UUID] | None = None
    safety_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def _one_source(self) -> RunCreate:
        has_text = bool(self.text and self.text.strip())
        if has_text == bool(self.file_ids):
            raise ValueError("Give either a non-empty 'text' or 'file_ids', not both.")
        return self


class RunStep(BaseModel):
    """One task of the run, in execution order."""

    task_id: UUID
    # parser, ner, relation, classification or safety.
    step: str
    service: str
    status: TaskStatus
    # True while it waits for the parser's pages.
    waiting: bool = False


class RunRead(BaseModel):
    """The run is a parent task: poll it (and its children) with /tasks."""

    id: UUID
    project_id: UUID
    status: TaskStatus
    steps: list[RunStep]
