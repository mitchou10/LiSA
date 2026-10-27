from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PageBboxCreate(BaseModel):
    """A box to blur on one page, as fractions of the page (0 to 1)."""

    page_number: int = Field(..., ge=1)
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    width: float = Field(..., gt=0, le=1)
    height: float = Field(..., gt=0, le=1)
    label: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def _inside_the_page(self) -> "PageBboxCreate":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("The box must stay inside the page.")
        return self


class PageBboxRead(PageBboxCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    created_by: str
    created_at: datetime
