"""What a project looks for: the definitions the detection services run.

Each table mirrors the input of one service: ``classification`` (labels, single
or multi), ``ner`` (entity types), ``relation`` (relation types) and ``safety``
(checks with labels, some of them meaning "nothing wrong").
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Action, Severity
from app.models.mixins import CreatedByMixin, TimestampMixin

THRESHOLD_CHECK = "threshold IS NULL OR (threshold >= 0 AND threshold <= 1)"


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _project_id() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# -- classification ----------------------------------------------------------
class ClassificationDefinition(Base, TimestampMixin, CreatedByMixin):
    """A classification run on every page: pick one label, or several."""

    __tablename__ = "classification_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_classification_name"),
        CheckConstraint(THRESHOLD_CHECK, name="ck_classification_threshold"),
    )

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = _project_id()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # False: exactly one label per page. True: every label that applies.
    multi_label: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Minimum score in multi-label mode; NULL uses the service default.
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="classifications")
    labels = relationship(
        "ClassificationLabel",
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="ClassificationLabel.position",
        lazy="selectin",
    )


class ClassificationLabel(Base):
    """A candidate label of a classification."""

    __tablename__ = "classification_labels"
    __table_args__ = (
        UniqueConstraint("definition_id", "name", name="uq_classification_label"),
    )

    id: Mapped[uuid.UUID] = _id()
    definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("classification_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # What the label means: helps the model tell similar labels apart.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    definition = relationship("ClassificationDefinition", back_populates="labels")


# -- entity extraction (ner) -------------------------------------------------
class EntityDefinition(Base, TimestampMixin, CreatedByMixin):
    """An entity type to find, and what to do when it is found."""

    __tablename__ = "entity_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "label", name="uq_entity_label"),
        CheckConstraint(THRESHOLD_CHECK, name="ck_entity_threshold"),
    )

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = _project_id()
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Grouping shown in the UI (PII, HEALTH, ...), stored upper case.
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="entity_severity"),
        nullable=False,
        default=Severity.MEDIUM,
    )
    action: Mapped[Action] = mapped_column(
        SAEnum(Action, name="entity_action"), nullable=False, default=Action.REDACT
    )
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="entities")


# -- relation extraction -----------------------------------------------------
class RelationDefinition(Base, TimestampMixin, CreatedByMixin):
    """A directional relation type to find (head -> tail)."""

    __tablename__ = "relation_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_relation_name"),
        CheckConstraint(THRESHOLD_CHECK, name="ck_relation_threshold"),
    )

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = _project_id()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Say which way it goes: "the head is a person, the tail the organization".
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="relations")


# -- safety ------------------------------------------------------------------
class SafetyDefinition(Base, TimestampMixin, CreatedByMixin):
    """A safety check run on every page (prompt safety, jailbreak, toxicity...)."""

    __tablename__ = "safety_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_safety_name"),
        CheckConstraint(THRESHOLD_CHECK, name="ck_safety_threshold"),
    )

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = _project_id()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    multi_label: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="safety_checks")
    labels = relationship(
        "SafetyLabel",
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="SafetyLabel.position",
        lazy="selectin",
    )


class SafetyLabel(Base):
    """A label of a safety check."""

    __tablename__ = "safety_labels"
    __table_args__ = (
        UniqueConstraint("definition_id", "name", name="uq_safety_label"),
    )

    id: Mapped[uuid.UUID] = _id()
    definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("safety_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True for a label meaning "nothing wrong" (safe, benign): any other label
    # makes the page unsafe.
    is_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    definition = relationship("SafetyDefinition", back_populates="labels")
