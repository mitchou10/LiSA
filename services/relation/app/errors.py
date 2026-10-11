"""Errors raised by the relation extraction service."""

from __future__ import annotations


class RelationError(ValueError):
    """The task cannot be processed (bad input, model failure)."""
