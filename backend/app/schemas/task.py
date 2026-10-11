from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import TaskStatus


class TaskBase(BaseModel):
    user_id: str = Field(..., max_length=255)
    input_data: dict = Field(default_factory=dict)
    service_id: UUID | None = None
    parent_task_id: UUID | None = None


class TaskSubmit(TaskBase):
    """Payload to submit a new task."""


class TaskUpdate(BaseModel):
    """Partial update of a task (status, progress, output, etc.)."""

    status: TaskStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    input_data: dict | None = None
    output_data: dict | None = None
    error: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_task_id: UUID | None
    service_id: UUID | None
    project_id: UUID | None = None
    user_id: str
    status: TaskStatus
    progress: int
    input_data: dict
    output_data: dict | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_seconds(self) -> float | None:
        """Compute time, once the task has started and ended."""
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, (self.finished_at - self.started_at).total_seconds())


class TaskStatusRead(BaseModel):
    """Lightweight view for polling a task's progress."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: TaskStatus
    progress: int
    error: str | None
