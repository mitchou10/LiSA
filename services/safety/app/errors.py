"""Errors raised by the safety service."""

from __future__ import annotations


class SafetyError(ValueError):
    """The task cannot be processed (bad input, model failure)."""
