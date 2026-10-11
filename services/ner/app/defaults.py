"""Entity types looked for when no detection profile can be fetched.

Mirrors the backend's seed profile (version 1): label, category, severity.
"""

from __future__ import annotations

from app.schemas import EntityRule

_GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "PII",
        "medium",
        [
            "person",
            "email address",
            "phone number",
            "physical address",
            "date of birth",
            "national ID",
        ],
    ),
    (
        "POLICE",
        "high",
        [
            "police report",
            "police officer",
            "suspect",
            "victim",
            "witness",
            "criminal record",
            "investigation information",
            "evidence",
        ],
    ),
    (
        "HEALTH",
        "medium",
        [
            "medical information",
            "medical record",
            "medical diagnosis",
            "medical history",
            "medication",
            "prescription",
        ],
    ),
    (
        "LEGAL",
        "medium",
        [
            "legal information",
            "court case",
            "court decision",
            "lawsuit",
            "legal proceeding",
            "lawyer",
            "judge",
            "prosecutor",
        ],
    ),
    ("SECRET", "high", ["password", "API key", "access token", "private key"]),
]

DEFAULT_ENTITIES = [
    EntityRule(label=label, category=category, severity=severity)  # type: ignore[arg-type]
    for category, severity, labels in _GROUPS
    for label in labels
]
