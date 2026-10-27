import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedByMixin, TimestampMixin


class BoxOverride(Base, TimestampMixin, CreatedByMixin):
    """A user's correction of one box of a detected entity.

    The ner output is never changed: the corrected box is kept here and used
    instead of the detected one, on screen and on export. An entity can have
    several boxes (one per line), hence ``bbox_index``. Coordinates are
    fractions of the page (0 to 1).
    """

    __tablename__ = "box_overrides"
    __table_args__ = (
        UniqueConstraint("run_id", "page_number", "entity_id", "bbox_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bbox_index: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
