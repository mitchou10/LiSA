"""Errors raised by the parser service."""

from __future__ import annotations


class ParserError(ValueError):
    """The task cannot be processed (bad input, too large, unsupported)."""


class StorageError(ParserError):
    """Object storage could not be read or written."""
