"""Initial detection settings, seeded as version 1 of each profile."""

from __future__ import annotations

from typing import Any

_PII = [
    "person",
    "email address",
    "phone number",
    "physical address",
    "date of birth",
    "national ID",
]
_POLICE = [
    "police report",
    "police officer",
    "suspect",
    "victim",
    "witness",
    "criminal record",
    "investigation information",
    "evidence",
]
_HEALTH = [
    "medical information",
    "medical record",
    "medical diagnosis",
    "medical history",
    "medication",
    "prescription",
]
_LEGAL = [
    "legal information",
    "court case",
    "court decision",
    "lawsuit",
    "legal proceeding",
    "lawyer",
    "judge",
    "prosecutor",
]
_SECRET = ["password", "API key", "access token", "private key"]

_GROUPS = [
    ("PII", "medium", _PII),
    ("POLICE", "high", _POLICE),
    ("HEALTH", "medium", _HEALTH),
    ("LEGAL", "medium", _LEGAL),
    ("SECRET", "high", _SECRET),
]


def gliner_default_config() -> dict[str, Any]:
    return {
        "threshold": 0.5,
        "entities": [
            {
                "label": label,
                "category": category,
                "severity": severity,
                "action": "redact",
                "enabled": True,
                "threshold": None,
            }
            for category, severity, labels in _GROUPS
            for label in labels
        ],
    }


# service_key -> (display name, description, default config factory)
DEFAULT_PROFILES = {
    "gliner-ner": (
        "Sensitive data (GLiNER)",
        (
            "Entity labels, categories, severities and actions used by the GLiNER "
            "named-entity service."
        ),
        gliner_default_config,
    ),
}
