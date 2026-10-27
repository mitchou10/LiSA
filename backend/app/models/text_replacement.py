import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import CreatedByMixin, TimestampMixin


def replacement_key(text: str) -> str:
    """What makes two texts "the same": same words, whatever the case or spacing."""
    return " ".join(text.split()).lower()


class TextReplacement(Base, TimestampMixin, CreatedByMixin):
    """The text to write instead of every entity of a run that reads the same.

    One row per distinct text (see ``replacement_key``), for the whole run:
    it is applied on every page, when the pages are exported.
    """

    __tablename__ = "text_replacements"
    __table_args__ = (UniqueConstraint("run_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(2000), nullable=False)
    replacement: Mapped[str] = mapped_column(String(255), nullable=False)
