from pydantic import BaseModel, Field


class Bbox(BaseModel):
    """Bounding box for detected entities in the input content."""

    id: str = Field(..., description="Unique identifier of the bounding box.")
    x: int = Field(
        ..., description="X-coordinate of the top-left corner of the bounding box."
    )
    y: int = Field(
        ..., description="Y-coordinate of the top-left corner of the bounding box."
    )
    width: int = Field(..., description="Width of the bounding box.")
    height: int = Field(..., description="Height of the bounding box.")


class Page(BaseModel):
    """Represents a page of content to analyze, with optional metadata."""

    content: str = Field(..., description="The text content of the page to analyze.")
    page_number: int | None = Field(
        None, description="Optional page number for multi-page documents."
    )
    bboxes: list[Bbox] | None = Field(
        None,
        description="Optional list of bounding boxes for detected entities in the page content.",
    )


class InputData(BaseModel):
    """Input payload for analysis tasks, containing the content to analyze and optional metadata."""

    metadata: dict | None = Field(
        None,
        description="Optional free-form metadata about the input (e.g. content type, source, etc.).",
    )
    pages: list[Page] | None = Field(
        default_factory=list,
        description="List of pages to analyze. For single-page inputs, provide a single page with the content.",
    )
