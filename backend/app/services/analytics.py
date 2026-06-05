"""Aggregation logic for the monitoring dashboard.

Detection results live inside each task's ``output_data`` JSON blob following the
``Analyse`` schema (``{ id, pages: [{ page_number, detections: [...] }] }``).
Rather than running database-specific JSON queries, we fetch the tasks in the
requested window and aggregate them in Python; this keeps the code portable
across PostgreSQL (prod) and SQLite (tests).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.analytics import (
    AlertItem,
    DashboardStats,
    DetectionTypeStat,
    SeverityStat,
    TimeBucket,
    UserStat,
)

# Maps the boolean discriminator field of each detector result to a stable
# type label exposed by the API / frontend.
DETECTION_TYPE_KEYS: dict[str, str] = {
    "jailbreak": "jailbreak",
    "prompt_injection": "prompt_injection",
    "secret_leak": "secret_leak",
    "sensitive_data_exposure": "sensitive_data_exposure",
    "toxic": "toxicity",
    "pii": "pii",
    "banned_topic": "banned_topic",
    "bias": "bias",
    "hallucination": "hallucination",
    "malicious_code": "malicious_code",
}

_ALERT_SEVERITIES = {"medium", "high"}
_MAX_ALERTS = 50


def _detection_type(detection: dict) -> str:
    """Infer a detection's type from its discriminator field."""
    for key, label in DETECTION_TYPE_KEYS.items():
        if key in detection:
            return label
    return "unknown"


def _iter_detections(task: Task):
    """Yield every detection dict found in a task's ``output_data``."""
    output = task.output_data
    if not isinstance(output, dict):
        return
    pages = output.get("pages")
    if not isinstance(pages, list):
        return
    for page in pages:
        if not isinstance(page, dict):
            continue
        detections = page.get("detections")
        if not isinstance(detections, list):
            continue
        for detection in detections:
            if isinstance(detection, dict):
                yield detection


class AnalyticsService:
    """Computes aggregated statistics for the dashboard."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)

    async def dashboard(
        self, *, user_id: str | None = None, days: int = 30
    ) -> DashboardStats:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        tasks = await self.tasks.list_since(since=since, user_id=user_id)

        acc = _Accumulator(since=since, days=days, now=now)
        for task in tasks:
            acc.ingest(task)

        return DashboardStats(
            user_id=user_id,
            since=since,
            generated_at=now,
            total_tasks=len(tasks),
            total_detections=acc.total_detections,
            total_flagged=acc.total_flagged,
            flagged_rate=(
                acc.total_flagged / acc.total_detections
                if acc.total_detections
                else 0.0
            ),
            by_type=acc.by_type(),
            by_severity=acc.by_severity_stats(),
            by_user=acc.by_user_stats(),
            timeseries=acc.timeseries(),
            alerts=acc.top_alerts(_MAX_ALERTS),
        )


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class _Accumulator:
    """Mutable aggregation state, fed one task at a time."""

    def __init__(self, *, since: datetime, days: int, now: datetime) -> None:
        self._now = now
        self.total_detections = 0
        self.total_flagged = 0
        self._type_total: dict[str, int] = defaultdict(int)
        self._type_flagged: dict[str, int] = defaultdict(int)
        self._severity: dict[str, int] = defaultdict(int)
        self._user_tasks: dict[str, int] = defaultdict(int)
        self._user_detections: dict[str, int] = defaultdict(int)
        self._user_flagged: dict[str, int] = defaultdict(int)
        self._alerts: list[AlertItem] = []
        # Pre-seed daily buckets so the chart has a continuous x-axis.
        self._buckets: dict[str, dict[str, int]] = {
            (since + timedelta(days=offset)).strftime("%Y-%m-%d"): {
                "tasks": 0,
                "detections": 0,
                "flagged": 0,
            }
            for offset in range(days + 1)
        }

    def ingest(self, task: Task) -> None:
        created = task.created_at or self._now
        day = created.strftime("%Y-%m-%d")
        bucket = self._buckets.get(day)
        if bucket is not None:
            bucket["tasks"] += 1
        self._user_tasks[task.user_id] += 1
        for detection in _iter_detections(task):
            self._ingest_detection(task, detection, created, bucket)

    def _ingest_detection(
        self,
        task: Task,
        detection: dict,
        created: datetime,
        bucket: dict[str, int] | None,
    ) -> None:
        self.total_detections += 1
        self._user_detections[task.user_id] += 1
        if bucket is not None:
            bucket["detections"] += 1

        dtype = _detection_type(detection)
        self._type_total[dtype] += 1

        if not detection.get("flagged"):
            return

        self.total_flagged += 1
        self._type_flagged[dtype] += 1
        self._user_flagged[task.user_id] += 1
        if bucket is not None:
            bucket["flagged"] += 1

        severity = detection.get("severity")
        if severity:
            self._severity[severity] += 1
        if severity in _ALERT_SEVERITIES:
            self._alerts.append(
                AlertItem(
                    task_id=task.id,
                    user_id=task.user_id,
                    type=dtype,
                    severity=severity,
                    action=detection.get("action"),
                    confidence=float(detection.get("confidence", 0.0)),
                    created_at=created,
                )
            )

    def by_type(self) -> list[DetectionTypeStat]:
        return [
            DetectionTypeStat(
                type=dtype,
                total=self._type_total[dtype],
                flagged=self._type_flagged.get(dtype, 0),
            )
            for dtype in sorted(
                self._type_total, key=lambda t: self._type_total[t], reverse=True
            )
        ]

    def by_severity_stats(self) -> list[SeverityStat]:
        return [
            SeverityStat(severity=sev, count=count)
            for sev, count in sorted(
                self._severity.items(),
                key=lambda kv: _SEVERITY_ORDER.get(kv[0], 99),
            )
        ]

    def by_user_stats(self) -> list[UserStat]:
        return [
            UserStat(
                user_id=uid,
                tasks=self._user_tasks[uid],
                detections=self._user_detections.get(uid, 0),
                flagged=self._user_flagged.get(uid, 0),
            )
            for uid in sorted(
                self._user_tasks,
                key=lambda u: self._user_flagged.get(u, 0),
                reverse=True,
            )
        ]

    def timeseries(self) -> list[TimeBucket]:
        return [
            TimeBucket(
                date=day,
                tasks=values["tasks"],
                detections=values["detections"],
                flagged=values["flagged"],
            )
            for day, values in sorted(self._buckets.items())
        ]

    def top_alerts(self, limit: int) -> list[AlertItem]:
        self._alerts.sort(
            key=lambda a: (
                _SEVERITY_ORDER.get(a.severity or "", 99),
                -a.created_at.timestamp(),
            )
        )
        return self._alerts[:limit]
