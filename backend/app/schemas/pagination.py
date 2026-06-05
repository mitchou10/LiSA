from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A paginated list response with the global total count."""

    items: list[T]
    total: int
    limit: int
    offset: int
