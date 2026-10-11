from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["low", "medium", "high"]
Action = Literal["allow", "redact", "block"]


class GlinerEntity(BaseModel):
    """One sensitive-data label GLiNER should look for."""

    label: str = Field(
        ..., min_length=1, max_length=100, description="Zero-shot label sent to GLiNER."
    )
    category: str = Field(
        ..., min_length=1, max_length=32, description="Grouping (PII, POLICE, ...)."
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="What the entity is, in plain words: sent to the model to "
        "improve accuracy.",
    )
    severity: Severity = "medium"
    action: Action = "redact"
    enabled: bool = True
    threshold: float | None = Field(
        default=None, ge=0, le=1, description="Overrides the global threshold."
    )

    @field_validator("label")
    @classmethod
    def _strip_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("label must not be blank")
        return value

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("category must not be blank")
        return value


class GlinerConfig(BaseModel):
    """Full editable configuration of the GLiNER service."""

    threshold: float = Field(default=0.5, ge=0, le=1)
    entities: list[GlinerEntity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_labels(self) -> GlinerConfig:
        seen: set[str] = set()
        for entity in self.entities:
            key = entity.label.lower()
            if key in seen:
                raise ValueError(f"duplicate label: '{entity.label}'")
            seen.add(key)
        return self


# service_key -> Pydantic model validating that service's config.
CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "gliner-ner": GlinerConfig,
}


class VersionCreate(BaseModel):
    config: dict
    comment: str | None = Field(default=None, max_length=1000)


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    config: dict
    comment: str | None
    created_by: str
    created_at: datetime
    is_active: bool = False


class ProfileRead(BaseModel):
    service_key: str
    name: str
    description: str | None
    active: VersionRead
    updated_at: datetime
