"""API contracts of projects and of what they look for (the catalog)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import Action, Severity

Threshold = Annotated[
    float | None, Field(ge=0, le=1, description="Minimum score (0-1).")
]


def _clean(value: str) -> str:
    return value.strip()


# -- projects ------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

    _strip = field_validator("name")(_clean)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class ProjectSummary(ProjectRead):
    """A project with how many things it looks for."""

    classifications: int = 0
    entities: int = 0
    relations: int = 0
    safety_checks: int = 0


# -- labels (classification and safety) ----------------------------------------
class LabelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    # Safety only: the label means "nothing wrong" (safe, benign).
    is_ok: bool = False

    _strip = field_validator("name")(_clean)


def _bare_strings(value: Any) -> Any:
    if isinstance(value, list):
        return [{"name": v} if isinstance(v, str) else v for v in value]
    return value


def _unique_labels(labels: list[LabelIn] | None) -> None:
    names = [lb.name.lower() for lb in labels or []]
    if len(set(names)) != len(names):
        raise ValueError("Label names must be unique.")


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    position: int
    is_ok: bool = False


# -- classification / safety: a task with labels --------------------------------
class _LabelledBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    multi_label: bool = False
    threshold: Threshold = None
    enabled: bool = True


class ClassificationCreate(_LabelledBase):
    labels: list[LabelIn] = Field(min_length=1)

    _strip = field_validator("name")(_clean)
    _bare = field_validator("labels", mode="before")(_bare_strings)

    @model_validator(mode="after")
    def _check(self) -> ClassificationCreate:
        _unique_labels(self.labels)
        return self


class ClassificationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    multi_label: bool | None = None
    threshold: Threshold = None
    enabled: bool | None = None
    # Replaces every label when given.
    labels: list[LabelIn] | None = Field(default=None, min_length=1)

    _bare = field_validator("labels", mode="before")(_bare_strings)

    @model_validator(mode="after")
    def _check(self) -> ClassificationUpdate:
        _unique_labels(self.labels)
        return self


class ClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    multi_label: bool
    threshold: float | None
    enabled: bool
    labels: list[LabelRead]
    created_by: str
    created_at: datetime
    updated_at: datetime


class SafetyCreate(ClassificationCreate):
    """A safety check: like a classification, with ``is_ok`` labels."""

    @model_validator(mode="after")
    def _has_an_ok_label(self) -> SafetyCreate:
        if not any(lb.is_ok for lb in self.labels):
            raise ValueError(
                "A safety check needs at least one label with is_ok=true "
                "(e.g. safe, benign): any other label makes a page unsafe."
            )
        return self


class SafetyUpdate(ClassificationUpdate):
    @model_validator(mode="after")
    def _has_an_ok_label(self) -> SafetyUpdate:
        if self.labels is not None and not any(lb.is_ok for lb in self.labels):
            raise ValueError("A safety check needs at least one label with is_ok=true.")
        return self


class SafetyRead(ClassificationRead):
    pass


# -- entities (ner) --------------------------------------------------------------
class EntityCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(default="OTHER", min_length=1, max_length=32)
    severity: Severity = Severity.MEDIUM
    action: Action = Action.REDACT
    threshold: Threshold = None
    enabled: bool = True

    _strip = field_validator("label")(_clean)

    @field_validator("category")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper() or "OTHER"


class EntityUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=32)
    severity: Severity | None = None
    action: Action | None = None
    threshold: Threshold = None
    enabled: bool | None = None

    @field_validator("label")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("category")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    label: str
    description: str | None
    category: str
    severity: Severity
    action: Action
    threshold: float | None
    enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


# -- relations ---------------------------------------------------------------------
class RelationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    threshold: Threshold = None
    enabled: bool = True

    _strip = field_validator("name")(_clean)


class RelationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    threshold: Threshold = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class RelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    threshold: float | None
    enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
