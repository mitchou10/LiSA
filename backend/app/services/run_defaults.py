"""The default run: what an analysis looks for without any project.

The same defaults every new project is seeded with (see
``app.services.project_defaults``), as lightweight objects the run pipeline
can feed to the workers directly: the PII entities for the ner step, the
GLiNER guardrails safety checks for the safety step. No project, no catalog
rows: nothing is written, nothing to configure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import Action, Severity
from app.services.project_defaults import default_pii_entities, default_safety_checks


@dataclass(frozen=True)
class _Label:
    name: str
    description: str | None = None
    is_ok: bool = False


@dataclass(frozen=True)
class DefaultEntity:
    """An entity definition, as the ner worker needs it."""

    label: str
    description: str | None
    category: str
    severity: Severity
    action: Action
    threshold: float | None = None
    enabled: bool = True
    labels: list[_Label] = field(default_factory=list)


@dataclass(frozen=True)
class DefaultSafetyCheck:
    """A safety check, as the safety worker needs it."""

    name: str
    description: str | None
    multi_label: bool
    threshold: float | None = None
    enabled: bool = True
    labels: list[_Label] = field(default_factory=list)


def default_definitions() -> dict[str, list[Any]]:
    """The definitions of a default run, by kind: entities and safety only.

    Relations and classifications have no defaults: a default run looks for
    personal information and guardrail violations, nothing else.
    """
    entities = [
        DefaultEntity(
            label=payload["label"],
            description=payload["description"],
            category=payload["category"],
            severity=Severity(payload["severity"]),
            action=Action(payload["action"]),
        )
        for payload in default_pii_entities()
    ]
    checks = [
        DefaultSafetyCheck(
            name=payload["name"],
            description=payload["description"],
            multi_label=payload["multi_label"],
            labels=[
                _Label(name=lb["name"], is_ok=lb["is_ok"]) for lb in payload["labels"]
            ],
        )
        for payload in default_safety_checks()
    ]
    return {"entities": entities, "safety": checks}
