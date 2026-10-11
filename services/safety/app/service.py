"""Safety service backed by llm-guard's input scanners.

Combines multiple scanners — PromptInjection, Toxicity, Secrets — into a
single worker that runs them all on each page and returns a unified
``Analyse`` result.  Each scanner produces its own detection entry so the
frontend can display per-scanner results side by side.
"""

from __future__ import annotations

import uuid
from typing import Any

from llm_guard.input_scanners import PromptInjection, Secrets, Toxicity
from worker.core.services.base import BaseService, TaskStatus

from app import config

# -- JSON Schemas (mirror the Anonymize service for compatibility) --------
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


def _severity_for(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class SafetyService(BaseService):
    """Detects prompt injection, toxicity, and secrets in prompts."""

    name = "llm-guard-safety"
    version = "0.1.0"
    description = (
        "Detects prompt injection, toxicity, and secrets/keys in prompts using "
        "llm-guard's PromptInjection, Toxicity, and Secrets input scanners."
    )
    tags = ["llm-guard", "safety", "prompt-injection", "toxicity", "secrets", "input"]
    type = "guard"
    queue = config.CELERY_QUEUE
    input_schema = INPUT_SCHEMA
    output_schema = OUTPUT_SCHEMA

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._scanners: dict[str, Any] = {}

    def _get_scanners(self) -> dict[str, Any]:
        """Lazily build the scanners (models are loaded once per worker)."""
        if self._scanners:
            return self._scanners

        enabled = {
            s.strip().lower() for s in config.ENABLED_SCANNERS.split(",") if s.strip()
        }

        if "prompt_injection" in enabled:
            self._scanners["prompt_injection"] = PromptInjection()
        if "toxicity" in enabled:
            self._scanners["toxicity"] = Toxicity()
        if "secrets" in enabled:
            self._scanners["secrets"] = Secrets()

        return self._scanners

    # -- per-scanner scan helpers -----------------------------------------
    @staticmethod
    def _scan_prompt_injection(
        scanner: PromptInjection, content: str
    ) -> dict[str, Any]:
        _, is_valid, risk_score = scanner.scan(content)
        flagged = not bool(is_valid)
        score = max(0.0, min(1.0, float(risk_score)))
        return {
            "flagged": flagged,
            "confidence": score,
            "severity": _severity_for(score) if flagged else None,
            "action": "block" if flagged else "allow",
            "service_id": None,  # filled by caller
            "pii": False,
            "entities": [],
            "classification": "prompt_injection",
            "details": {"scanner": "PromptInjection", "risk_score": score},
        }

    @staticmethod
    def _scan_toxicity(scanner: Toxicity, content: str) -> dict[str, Any]:
        _, is_valid, risk_score = scanner.scan(content)
        flagged = not bool(is_valid)
        score = max(0.0, min(1.0, float(risk_score)))
        return {
            "flagged": flagged,
            "confidence": score,
            "severity": _severity_for(score) if flagged else None,
            "action": "block" if flagged else "allow",
            "service_id": None,
            "pii": False,
            "entities": [],
            "classification": "toxicity",
            "details": {"scanner": "Toxicity", "risk_score": score},
        }

    @staticmethod
    def _scan_secrets(scanner: Secrets, content: str) -> dict[str, Any]:
        sanitized, is_valid, risk_score = scanner.scan(content)
        flagged = not bool(is_valid)
        score = max(0.0, min(1.0, float(risk_score)))

        # Secrets scanner redacts found secrets in the sanitized text.
        # We try to locate them in the original to build entities.
        entities: list[dict[str, Any]] = []
        if flagged and sanitized != content:
            # Find redacted placeholders like [REDACTED_SECRET_1] in sanitized
            import re

            placeholders = list(re.finditer(r"\[REDACTED_[A-Z_]+_\d+\]", sanitized))
            for idx, match in enumerate(placeholders):
                entities.append(
                    {
                        "id": f"e{idx}",
                        "type": "SECRET",
                        "text": match.group(),
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "flagged": True,
                        "confidence": score,
                    }
                )

        return {
            "flagged": flagged,
            "confidence": score,
            "severity": _severity_for(score) if flagged else None,
            "action": "redact" if flagged else "allow",
            "service_id": None,
            "pii": False,
            "entities": entities,
            "classification": "secret_leak",
            "details": {"scanner": "Secrets", "risk_score": score},
        }

    # -- page-level scanning ----------------------------------------------
    def _scan_page(self, content: str) -> list[dict[str, Any]]:
        """Run all enabled scanners on one page and return detection dicts."""
        scanners = self._get_scanners()
        detections: list[dict[str, Any]] = []

        if "prompt_injection" in scanners:
            det = self._scan_prompt_injection(scanners["prompt_injection"], content)
            det["service_id"] = self.id
            detections.append(det)

        if "toxicity" in scanners:
            det = self._scan_toxicity(scanners["toxicity"], content)
            det["service_id"] = self.id
            detections.append(det)

        if "secrets" in scanners:
            det = self._scan_secrets(scanners["secrets"], content)
            det["service_id"] = self.id
            detections.append(det)

        return detections

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
                detections = self._scan_page(content)
                results.append(
                    {
                        "page_number": (
                            page.get("page_number") if isinstance(page, dict) else None
                        ),
                        "detections": detections,
                    }
                )
                progress = round((index + 1) / total * 100)
                self.update_task(task_id, progress=progress)
        except Exception as exc:
            self.update_task(task_id, status=TaskStatus.ERROR, error=str(exc))
            raise

        analyse = {
            "id": task_id or f"safety-{uuid.uuid4()}",
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
