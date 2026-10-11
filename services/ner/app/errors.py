"""Errors raised by the NER service."""

from __future__ import annotations


class NerError(ValueError):
    """The task cannot be processed (bad input, model failure)."""
