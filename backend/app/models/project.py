import uuid

from sqlalchemy import String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedByMixin, TimestampMixin


class Project(Base, TimestampMixin, CreatedByMixin):
    """A workspace grouping the files, the tasks and what to look for in them.

    What to look for is defined per project: classifications, entity types,
    relation types and safety checks (see ``app.models.catalog``).
    """

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("created_by", "name", name="uq_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    classifications = relationship(
        "ClassificationDefinition",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    entities = relationship(
        "EntityDefinition", back_populates="project", cascade="all, delete-orphan"
    )
    relations = relationship(
        "RelationDefinition", back_populates="project", cascade="all, delete-orphan"
    )
    safety_checks = relationship(
        "SafetyDefinition", back_populates="project", cascade="all, delete-orphan"
    )
