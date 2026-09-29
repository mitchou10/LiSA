"""GLiNER service: zero-shot multilingual NER for custom entity types.

Uses the GLiNER model to detect entities from a configurable list of labels
(PII, police, health, legal, secrets, ...). Each detected entity is mapped
to a high-level category via ``CATEGORY_MAP`` so the frontend can group and
color-code results.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from worker.core.services.base import BaseService, TaskStatus

from worker.core.client.detection_profiles import DetectionProfileClient

from app import config
from app.profile import Profile, ProfileProvider

logger = logging.getLogger("lisa.service.gliner")

# -- JSON Schemas (mirror the other services for compatibility) -----------
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

# -- Category mapping -----------------------------------------------------
# Maps each GLiNER label to a high-level category. The category is used by
# the frontend to pick a color/label (via ENTITY_TYPE_MAP in resultAdapter.js).
CATEGORY_MAP: dict[str, str] = {
    # PII
    "person": "PII",
    "email address": "PII",
    "phone number": "PII",
    "physical address": "PII",
    "date of birth": "PII",
    "national ID": "PII",
    # Police
    "police report": "POLICE",
    "police officer": "POLICE",
    "suspect": "POLICE",
    "victim": "POLICE",
    "witness": "POLICE",
    "criminal record": "POLICE",
    "investigation information": "POLICE",
    "evidence": "POLICE",
    # Santé
    "medical information": "HEALTH",
    "medical record": "HEALTH",
    "medical diagnosis": "HEALTH",
    "medical history": "HEALTH",
    "medication": "HEALTH",
    "prescription": "HEALTH",
    # Juridique
    "legal information": "LEGAL",
    "court case": "LEGAL",
    "court decision": "LEGAL",
    "lawsuit": "LEGAL",
    "legal proceeding": "LEGAL",
    "lawyer": "LEGAL",
    "judge": "LEGAL",
    "prosecutor": "LEGAL",
    # Secrets
    "password": "SECRET",
    "API key": "SECRET",
    "access token": "SECRET",
    "private key": "SECRET",
}


_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
_ACTION_RANK = {"allow": 0, "redact": 1, "block": 2}


def _severity_for_category(category: str) -> str:
    """Default severity per category, used when no remote profile is available."""
    if category in ("SECRET", "POLICE"):
        return "high"
    if category in ("PII", "HEALTH", "LEGAL"):
        return "medium"
    return "low"


class GlinerService(BaseService):
    """Zero-shot NER service using GLiNER for custom entity detection."""

    name = "gliner-ner"
    version = "0.1.0"
    description = (
        "Zero-shot multilingual Named Entity Recognition using GLiNER. "
        "Detects PII, police, health, legal, and secret entities from a "
        "configurable list of labels."
    )
    tags = ["gliner", "ner", "pii", "police", "health", "legal", "secrets", "multilingual"]
    type = "analyser"
    queue = config.CELERY_QUEUE
    input_schema = INPUT_SCHEMA
    output_schema = OUTPUT_SCHEMA

    def __init__(
        self, *, profile_provider: ProfileProvider | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._model = None
        self._labels: list[str] | None = None
        self._profiles = profile_provider or self._build_profile_provider()

    # -- detection profile ---------------------------------------------------
    def _build_profile_provider(self) -> ProfileProvider:
        """Live profile from the backend when enabled, else env defaults."""
        fetch = None
        if config.profile_enabled():
            client = DetectionProfileClient()
            fetch = lambda: client.get_active_config(config.PROFILE_KEY)  # noqa: E731
        return ProfileProvider(
            service_key=config.PROFILE_KEY,
            fallback=self._default_profile,
            fetch=fetch,
            redis_url=config.REDIS_URL if fetch else None,
            channel=config.PROFILE_CHANNEL,
            refresh_seconds=config.PROFILE_REFRESH_SECONDS,
        )

    def _default_profile(self) -> Profile:
        """Profile derived from the environment (used until/unless remote)."""
        return {
            "version": None,
            "threshold": config.GLINER_THRESHOLD,
            "entities": [
                {
                    "label": label,
                    "category": CATEGORY_MAP.get(label, "OTHER"),
                    "severity": _severity_for_category(
                        CATEGORY_MAP.get(label, "OTHER")
                    ),
                    "action": "redact",
                    "enabled": True,
                    "threshold": None,
                }
                for label in self._get_labels()
            ],
        }

    def _get_labels(self) -> list[str]:
        """Parse the comma-separated label list from config."""
        if self._labels is None:
            self._labels = [
                lbl.strip()
                for lbl in config.GLINER_LABELS.split(",")
                if lbl.strip()
            ]
        return self._labels

    def _get_model(self):
        """Lazily load the GLiNER model (downloaded once per worker)."""
        if self._model is None:
            from gliner import GLiNER

            logger.info("Loading GLiNER model: %s", config.GLINER_MODEL)
            self._model = GLiNER.from_pretrained(config.GLINER_MODEL)
            logger.info("GLiNER model loaded")
        return self._model

    # -- page-level scanning ----------------------------------------------
    def _scan_page(self, content: str) -> dict[str, Any]:
        """Run GLiNER on one page and return a detection dict."""
        profile = self._profiles.get()
        rules = {
            e["label"]: e for e in profile["entities"] if e.get("enabled", True)
        }
        labels = list(rules)
        global_threshold = float(profile["threshold"])

        entities_raw: list[dict[str, Any]] = []
        if labels:
            # Query with the lowest threshold in play, then filter per label.
            floor = min(
                [global_threshold]
                + [r["threshold"] for r in rules.values() if r.get("threshold") is not None]
            )
            entities_raw = self._get_model().predict_entities(
                content, labels, threshold=floor
            )

        entities: list[dict[str, Any]] = []
        for ent in entities_raw:
            label = ent.get("label", "unknown")
            rule = rules.get(label, {})
            threshold = rule.get("threshold")
            score = float(ent.get("score", 0.0))
            if score < (global_threshold if threshold is None else threshold):
                continue
            action = rule.get("action", "redact")
            entities.append(
                {
                    "id": f"e{len(entities)}",
                    "type": rule.get("category", CATEGORY_MAP.get(label, "OTHER")),
                    "label": label,  # original GLiNER label
                    "text": ent.get("text", ""),
                    "start_char": ent.get("start", -1),
                    "end_char": ent.get("end", -1),
                    "flagged": action != "allow",
                    "confidence": score,
                    "severity": rule.get("severity", "low"),
                    "action": action,
                }
            )

        flagged_entities = [e for e in entities if e["flagged"]]
        flagged = len(flagged_entities) > 0
        return {
            "flagged": flagged,
            "confidence": max((e["confidence"] for e in flagged_entities), default=0.0),
            "severity": max(
                (e["severity"] for e in flagged_entities),
                key=_SEVERITY_RANK.__getitem__,
            )
            if flagged
            else None,
            "action": max(
                (e["action"] for e in flagged_entities),
                key=_ACTION_RANK.__getitem__,
            )
            if flagged
            else "allow",
            "service_id": self.id,
            "pii": any(e["type"] == "PII" for e in entities),
            "entities": entities,
            "classification": "gliner_ner",
            "profile_version": profile.get("version"),
            "details": {
                "model": config.GLINER_MODEL,
                "labels": labels,
                "num_entities": len(entities),
                "profile_version": profile.get("version"),
            },
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
            "id": task_id or f"gliner-{uuid.uuid4()}",
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
