from pydantic import BaseModel, Field


class OutputSchema(BaseModel):
    """
    Schema for output data validation.
    """

    process_time: float = Field(
        ..., description="The time taken to process the request."
    )
    metadata: dict = Field(
        default_factory=dict, description="Additional metadata about the processing."
    )


class SingleGuardOutputSchema(OutputSchema):
    content: str = Field(..., description="The processed content.")
    predictions: dict[str, bool] = Field(
        ..., description="Predictions for each scanner."
    )
    scores: dict[str, float] = Field(..., description="Scores for each scanner.")


class BatchGuardOutputSchema(OutputSchema):
    results: list[SingleGuardOutputSchema] = Field(
        ..., description="List of results for each input in the batch."
    )


class SingleAnalyserOutputSchema(OutputSchema):
    content: str = Field(..., description="The processed content.")
    predictions: dict[str, float] = Field(
        default_factory=dict, description="Predictions for each scanner."
    )


class BatchAnalyserOutputSchema(OutputSchema):
    results: list[SingleAnalyserOutputSchema] = Field(
        ..., description="List of results for each input in the batch."
    )
