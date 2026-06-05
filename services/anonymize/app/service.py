"""Anonymize service backed by llm-guard's ``Anonymize`` input scanner.

``process`` consumes an ``InputData``-shaped payload (``pages[].content``),
iterates over the pages, and returns an ``Analyse``-shaped result
(``pages[].detections`` with PII entities). Progress and status are reported
to the backend task as pages are processed.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from llm_guard.input_scanners import Anonymize
from llm_guard.vault import Vault
from worker.core.services.base import BaseService, TaskStatus

from app import config

# -- JSON Schemas advertised on registration (mirror backend InputData/Analyse).
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "InputData",
    "properties": {
        "metadata": {"type": ["object", "null"]},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "page_number": {"type": ["integer", "null"]},
                    "bboxes": {"type": ["array", "null"]},
                },
                "required": ["content"],
            },
        },
    },
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Analyse",
    "properties": {
        "id": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": ["integer", "null"]},
                    "detections": {"type": "array"},
                },
            },
        },
        "error": {"type": ["string", "null"]},
    },
}

_PLACEHOLDER_RE = re.compile(r"\[REDACTED_(?P<type>[A-Z_]+?)_\d+\]")


def _severity_for(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _entity_type(placeholder: str) -> str:
    match = _PLACEHOLDER_RE.search(placeholder)
    return match.group("type") if match else "UNKNOWN"


class AnonymizeService(BaseService):
    """Redacts PII from prompts using Presidio-backed detection."""

    name = "llm-guard-anonymize"
    version = "0.1.0"
    description = "Redacts PII (names, emails, cards, IBAN, SSN, ...) from prompts using llm-guard's Anonymize scanner."
    tags = ["llm-guard", "pii", "anonymize", "input"]
    type = "guard"
    queue = config.CELERY_QUEUE
    input_schema = INPUT_SCHEMA
    output_schema = OUTPUT_SCHEMA

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._scanner = None
        self._vault = None

    def _get_scanner(self):
        """Lazily build the Anonymize scanner and its Vault."""
        if self._scanner is None:
            self._vault = Vault()
            self._scanner = Anonymize(
                self._vault,
                threshold=config.ANONYMIZE_THRESHOLD,
                language=config.ANONYMIZE_LANGUAGE,
            )
        return self._scanner

    # -- page-level scanning ----------------------------------------------
    def _scan_page(self, content: str) -> dict[str, Any]:
        """Scan one page's content and return a PIIDetectionResult dict."""
        scanner = self._get_scanner()
        before = len(self._vault.get())
        sanitized, is_valid, risk_score = scanner.scan(content)
        new_entries = self._vault.get()[before:]

        flagged = not bool(is_valid)
        # llm-guard returns a risk score in [-1, 1] (negative when valid); clamp
        # it to a [0, 1] confidence so the UI never shows a negative score.
        score = max(0.0, min(1.0, float(risk_score)))

        entities = []
        for idx, (placeholder, original) in enumerate(new_entries):
            start = content.find(original)
            entities.append(
                {
                    "id": f"e{idx}",
                    "type": _entity_type(placeholder),
                    "text": original,
                    "start_char": start,
                    "end_char": start + len(original) if start >= 0 else -1,
                    "flagged": True,
                    "confidence": score,
                }
            )

        return {
            "flagged": flagged,
            "confidence": score,
            "severity": _severity_for(score) if flagged else None,
            "action": "redact" if flagged else "allow",
            "service_id": self.id,
            "pii": flagged,
            "entities": entities or None,
            "details": {"sanitized": sanitized, "risk_score": score},
        }

    def _iter_pages(self, input_data: Any) -> list[dict[str, Any]]:
        """Normalize a flexible payload into a list of page dicts."""
        if isinstance(input_data, str):
            return [{"content": input_data, "page_number": None}]
        if isinstance(input_data, dict):
            pages = input_data.get("pages")
            if pages:
                return pages
            if input_data.get("prompt") or input_data.get("content"):
                return [
                    {
                        "content": str(
                            input_data.get("prompt") or input_data.get("content")
                        ),
                        "page_number": None,
                    }
                ]
        return [{"content": str(input_data), "page_number": None}]

    def process(self, input_data: Any, task_id: str | None = None) -> dict[str, Any]:
        """Iterate over pages, scan each, and report progress/status."""
        pages = self._iter_pages(input_data)
        total = len(pages) or 1

        self.update_task(task_id, status=TaskStatus.RUNNING, progress=0)

        results: list[dict[str, Any]] = []
        try:
            for index, page in enumerate(pages):
                content = (
                    str(page.get("content", ""))
                    if isinstance(page, dict)
                    else str(page)
                )
                detection = self._scan_page(content)
                results.append(
                    {
                        "page_number": (
                            page.get("page_number") if isinstance(page, dict) else None
                        ),
                        "detections": [detection],
                    }
                )
                progress = round((index + 1) / total * 100)
                self.update_task(task_id, progress=progress)
        except Exception as exc:  # noqa: BLE001 - mark the task failed and re-raise
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        analyse = {
            "id": task_id or f"anonymize-{uuid.uuid4()}",
            "pages": results,
            "error": None,
        }
        self.update_task(
            task_id,
            status=TaskStatus.SUCCESS,
            progress=100,
            output_data=analyse,
        )
        return analyse
