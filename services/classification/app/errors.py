"""Errors raised by the classification service."""

from __future__ import annotations


class ClassificationError(ValueError):
    """The task cannot be processed (bad input, unknown backend, model failure)."""
