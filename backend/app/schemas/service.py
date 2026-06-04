from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ServiceType


class ServiceBase(BaseModel):
    name: str = Field(..., max_length=255)
    version: str = Field(default="0.1.0", max_length=50)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    type: ServiceType = ServiceType.OTHER
    input_schema: dict = Field(default_factory=dict, description="JSON Schema")
    output_schema: dict = Field(default_factory=dict, description="JSON Schema")


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=50)
    description: str | None = None
    tags: list[str] | None = None
    type: ServiceType | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None


class ServiceRead(ServiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
