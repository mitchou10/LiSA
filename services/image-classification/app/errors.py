"""Errors raised by the image classification service."""

from __future__ import annotations


class ImageClassificationError(ValueError):
    """The task cannot be processed (bad input, unreadable image, model failure)."""
