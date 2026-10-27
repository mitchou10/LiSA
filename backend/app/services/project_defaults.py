"""What every new project starts with, seeded at project creation.

Two kinds of defaults, both plain catalog rows the user can edit or delete:

* safety checks, mirroring the safety worker's own defaults
  (``services/safety/app/defaults.py``) so a fresh project runs the GLiNER2
  guardrails checkpoint out of the box: prompt safety, jailbreak /
  prompt-injection detection and toxicity;
* PII entities, mirroring the ner seed profile
  (``app.services.detection_defaults``) so personal information is looked for
  without any setup: names, emails, phone numbers, IDs, secrets...
"""

from __future__ import annotations

from typing import Any

# (name, description, multi_label, labels) - labels: (name, is_ok)
_DEFAULT_SAFETY_CHECKS: list[dict[str, Any]] = [
    {
        "name": "prompt_safety",
        "description": "Is the prompt safe to run?",
        "multi_label": False,
        "labels": [("safe", True), ("unsafe", False)],
    },
    {
        "name": "jailbreak_detection",
        "description": "Prompt injection, jailbreak and exfiltration attempts.",
        "multi_label": True,
        "labels": [
            ("prompt_injection", False),
            ("jailbreak_attempt", False),
            ("policy_evasion", False),
            ("instruction_override", False),
            ("system_prompt_exfiltration", False),
            ("data_exfiltration", False),
            ("roleplay_bypass", False),
            ("hypothetical_bypass", False),
            ("obfuscated_attack", False),
            ("multi_step_attack", False),
            ("social_engineering", False),
            ("benign", True),
        ],
    },
    {
        "name": "prompt_toxicity",
        "description": "Harmful content: violence, hate, sexual, self-harm...",
        "multi_label": True,
        "labels": [
            ("violence_and_weapons", False),
            ("non_violent_crime", False),
            ("sexual_content", False),
            ("hate_and_discrimination", False),
            ("self_harm_and_suicide", False),
            ("child_safety", False),
            ("misinformation", False),
            ("unethical_conduct", False),
            ("benign", True),
        ],
    },
]


# (label, description, category, severity, action) - personal information the
# ner step looks for in every new project.
_DEFAULT_PII_ENTITIES: list[dict[str, Any]] = [
    {
        "label": "person",
        "description": "A person's full name.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
    },
    {
        "label": "email address",
        "description": "An email address.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
    },
    {
        "label": "phone number",
        "description": "A phone or fax number.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
    },
    {
        "label": "physical address",
        "description": "A postal or home address.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
    },
    {
        "label": "date of birth",
        "description": "A person's date of birth.",
        "category": "PII",
        "severity": "medium",
        "action": "redact",
    },
    {
        "label": "national ID",
        "description": "A national identifier (social security, ID number).",
        "category": "PII",
        "severity": "high",
        "action": "redact",
    },
    {
        "label": "iban",
        "description": "An international bank account number.",
        "category": "PII",
        "severity": "high",
        "action": "redact",
    },
    {
        "label": "payment card",
        "description": "A credit or debit card number.",
        "category": "PII",
        "severity": "high",
        "action": "redact",
    },
    {
        "label": "password",
        "description": "A password or passphrase.",
        "category": "SECRET",
        "severity": "high",
        "action": "redact",
    },
    {
        "label": "api key",
        "description": "An API key or access token.",
        "category": "SECRET",
        "severity": "high",
        "action": "redact",
    },
]


def default_safety_checks() -> list[dict[str, Any]]:
    """The safety checks seeded into every new project, as catalog payloads."""
    return [
        {
            "name": check["name"],
            "description": check["description"],
            "multi_label": check["multi_label"],
            "enabled": True,
            "labels": [
                {"name": name, "is_ok": is_ok} for name, is_ok in check["labels"]
            ],
        }
        for check in _DEFAULT_SAFETY_CHECKS
    ]


def default_pii_entities() -> list[dict[str, Any]]:
    """The PII entities seeded into every new project, as catalog payloads."""
    return [
        {
            "label": entity["label"],
            "description": entity["description"],
            "category": entity["category"],
            "severity": entity["severity"],
            "action": entity["action"],
            "enabled": True,
        }
        for entity in _DEFAULT_PII_ENTITIES
    ]
