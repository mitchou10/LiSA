import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

# JSONB on PostgreSQL, generic JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class DetectionProfile(Base, TimestampMixin):
    """The editable detection settings of one service (e.g. GLiNER labels).

    The profile itself is only a stable handle; the settings live in the
    append-only :class:`DetectionProfileVersion` rows. The current settings
    are those of the highest version.
    """

    __tablename__ = "detection_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list["DetectionProfileVersion"]] = relationship(
        back_populates="profile",
        order_by="DetectionProfileVersion.version",
        cascade="all, delete-orphan",
    )


class DetectionProfileVersion(Base):
    """One immutable snapshot of a profile's settings."""

    __tablename__ = "detection_profile_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_profile_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detection_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict] = mapped_column(JSONType, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped[DetectionProfile] = relationship(back_populates="versions")
