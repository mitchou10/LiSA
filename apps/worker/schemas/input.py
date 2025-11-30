from pydantic import BaseModel, Field


class InputSchema(BaseModel):
    """
    Schema for input data validation.
    """

    extras: dict = Field(
        default_factory=dict, description="Additional parameters for processing."
    )


class SingleAnalyserInputSchema(InputSchema):
    content: str = Field(..., description="The text content to be analyzed.")
    candidate_labels: list[str] = Field(
        default_factory=lambda: ["santé", "finance", "éducation", "cybersécurité"],
        description="List of candidate labels for classification.",
    )


class BatchAnalyserInputSchema(InputSchema):
    content: list[str] = Field(..., description="List of text contents to be analyzed.")
    candidate_labels: list[str] = Field(
        default_factory=lambda: ["santé", "finance", "éducation", "cybersécurité"],
        description="List of candidate labels for classification.",
    )
