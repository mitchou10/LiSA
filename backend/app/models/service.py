import uuid

from sqlalchemy import JSON, Enum as SAEnum
from sqlalchemy import String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ServiceType
from app.models.mixins import TimestampMixin

# JSONB on PostgreSQL, generic JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Service(Base, TimestampMixin):
    """A registered processing service (worker) with its I/O contracts."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.1.0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type"),
        nullable=False,
        default=ServiceType.OTHER,
    )
    input_schema: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
