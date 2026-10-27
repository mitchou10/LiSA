"""What a user changes on a finished run, on top of what the workers found."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.page_bbox import BoxGeometry


class ReplacementSet(BaseModel):
    """The text to write instead of every entity that reads ``text``.

    "Reads the same" ignores case and spacing. An empty ``replacement`` removes
    the replacement of that text.
    """

    text: str = Field(..., min_length=1, max_length=2000)
    replacement: str = Field("", max_length=255)


class ReplacementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    replacement: str


class BoxOverrideSet(BoxGeometry):
    """The corrected position of one box of a detected entity."""

    page_number: int = Field(..., ge=1)
    entity_id: str = Field(..., min_length=1, max_length=64)
    bbox_index: int = Field(0, ge=0)


class BoxOverrideRead(BoxOverrideSet):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    created_at: datetime
