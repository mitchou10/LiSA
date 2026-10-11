class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class ConflictError(Exception):
    """Raised when an operation conflicts with the current state."""


class InvalidStateError(Exception):
    """Raised when an operation is not allowed in the current state."""


class GoneError(Exception):
    """Raised when a resource existed but its content has been deleted."""
