import enum


class TaskStatus(str, enum.Enum):
    """Lifecycle states of a task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    REVOKED = "revoked"


class ServiceType(str, enum.Enum):
    """High-level category of a service."""

    GUARD = "guard"
    ANALYSER = "analyser"
    OTHER = "other"


class UserRole(str, enum.Enum):
    """Access level of a user account."""

    ADMIN = "admin"
    USER = "user"


class Severity(str, enum.Enum):
    """How serious a finding is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Action(str, enum.Enum):
    """What to do with a finding."""

    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"
