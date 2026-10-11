from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: str
    filename: str
    mime: str | None = None
    size: int
    sha256: str
    created_at: datetime
