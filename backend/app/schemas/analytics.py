from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DetectionTypeStat(BaseModel):
    """Aggregated counts for a single detection type (e.g. jailbreak, pii)."""

    type: str = Field(..., description="Detection type key.")
    total: int = Field(..., description="Number of detection results of this type.")
    flagged: int = Field(..., description="How many of them were flagged.")


class SeverityStat(BaseModel):
    severity: str = Field(..., description="Severity bucket: low, medium, high.")
    count: int = Field(..., description="Number of flagged detections at this level.")


class TimeBucket(BaseModel):
    """One point of the time-series, bucketed by day."""

    date: str = Field(..., description="Bucket date (YYYY-MM-DD).")
    tasks: int = Field(..., description="Tasks created during this day.")
    detections: int = Field(..., description="Detection results produced this day.")
    flagged: int = Field(..., description="Flagged detections produced this day.")


class UserStat(BaseModel):
    user_id: str = Field(..., description="User identifier.")
    tasks: int = Field(..., description="Tasks submitted by the user.")
    detections: int = Field(..., description="Detection results for the user.")
    flagged: int = Field(..., description="Flagged detections for the user.")


class AlertItem(BaseModel):
    """A noteworthy (flagged, medium/high) detection surfaced as an alert."""

    task_id: UUID
    user_id: str
    type: str
    severity: str | None = None
    action: str | None = None
    confidence: float
    created_at: datetime


class DashboardStats(BaseModel):
    """Aggregated analytics for the monitoring dashboard."""

    user_id: str | None = Field(
        None, description="User the stats are scoped to (null = all users)."
    )
    since: datetime = Field(..., description="Start of the analysed window.")
    generated_at: datetime = Field(..., description="When the stats were computed.")

    total_tasks: int = 0
    total_detections: int = 0
    total_flagged: int = 0
    flagged_rate: float = Field(
        0.0, description="Flagged detections over total detections (0.0–1.0)."
    )

    by_type: list[DetectionTypeStat] = Field(default_factory=list)
    by_severity: list[SeverityStat] = Field(default_factory=list)
    by_user: list[UserStat] = Field(default_factory=list)
    timeseries: list[TimeBucket] = Field(default_factory=list)
    alerts: list[AlertItem] = Field(default_factory=list)
