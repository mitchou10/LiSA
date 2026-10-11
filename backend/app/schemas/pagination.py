from __future__ import annotations

from pydantic import BaseModel


class Page[T](BaseModel):
    """A paginated list response with the global total count."""

    items: list[T]
    total: int
    limit: int
    offset: int
