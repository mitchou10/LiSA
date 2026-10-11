import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaskStatus
from app.models.mixins import TimestampMixin

# JSONB on PostgreSQL, generic JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Task(Base, TimestampMixin):
    """A unit of work, optionally part of a parent/child execution graph."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_data: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    output_data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent: Mapped["Task | None"] = relationship(
        "Task",
        remote_side=lambda: [Task.id],
        back_populates="children",
    )
    children: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
