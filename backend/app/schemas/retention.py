"""How long runs are kept, and when one was purged."""

from datetime import datetime

from pydantic import BaseModel


class PurgeRead(BaseModel):
    purged_at: datetime


class RetentionRead(BaseModel):
    """``days``: how long a finished run keeps its content (0: until purged by hand)."""

    days: int
