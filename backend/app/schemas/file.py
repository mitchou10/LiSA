from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: str
    filename: str
    mime: str | None = None
    size: int
    sha256: str
    # Key in the bucket: what services such as the parser take as input.
    s3_key: str = Field(validation_alias="storage_key")
    created_at: datetime
