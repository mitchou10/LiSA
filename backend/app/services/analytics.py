"""Aggregation logic for the monitoring dashboard.

What the services found lives inside each task's ``output_data`` JSON blob.
Two shapes are read:

* the current services: ``ner`` puts ``entities`` on each page, ``safety`` a
  ``safety`` list of checks (each flagged or not);
* the former ``Analyse`` schema (``pages[].detections[]``), kept so that tasks
  stored before the migration still count.

Rather than running database-specific JSON queries, we fetch the tasks in the
requested window and aggregate them in Python; this keeps the code portable
across PostgreSQL (prod) and SQLite (tests).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.project import Project
from app.models.service import Service
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.analytics import (
    AlertItem,
    DashboardStats,
    DetectionTypeStat,
    ProjectStat,
    ServiceStat,
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
    if isinstance(detection.get("type"), str):
        return detection["type"]
    for key, label in DETECTION_TYPE_KEYS.items():
        if key in detection:
            return label
    return "unknown"


def _entity_detection(entity: dict) -> dict:
    """An entity found by the ner service, as a detection of its category."""
    return {
        "type": f"entity:{entity.get('category', 'OTHER')}",
        "flagged": bool(entity.get("flagged")),
        "severity": entity.get("severity"),
        "action": entity.get("action"),
        "confidence": entity.get("score") or 0.0,
    }


def _safety_detection(check: dict) -> dict:
    """One safety check on one page: a detection, flagged when a label is."""
    flagged = bool(check.get("flagged"))
    scores = [
        label.get("score") or 0.0
        for label in check.get("labels") or []
        if label.get("flagged")
    ]
    return {
        "type": f"safety:{check.get('name', 'check')}",
        "flagged": flagged,
        # A safety check has no severity of its own: a hit is serious.
        "severity": "high" if flagged else None,
        "action": "block" if flagged else "allow",
        "confidence": max(scores, default=0.0),
    }


def _iter_detections(task: Task):
    """Yield every detection found in a task's ``output_data``."""
    output = task.output_data
    if not isinstance(output, dict):
        return
    pages = output.get("pages")
    if not isinstance(pages, list):
        return
    for page in pages:
        if not isinstance(page, dict):
            continue
        for entity in page.get("entities") or []:
            if isinstance(entity, dict):
                yield _entity_detection(entity)
        for check in page.get("safety") or []:
            if isinstance(check, dict):
                yield _safety_detection(check)
        detections = page.get("detections")
        if not isinstance(detections, list):
            continue
        for detection in detections:
            if isinstance(detection, dict):
                yield detection


def _seconds(task: Task) -> float | None:
    """Compute time of a finished task."""
    if task.started_at is None or task.finished_at is None:
        return None
    return max(0.0, (task.finished_at - task.started_at).total_seconds())


def _is_run(task: Task) -> bool:
    """The parent task of a run: a project run or a default run."""
    return (
        task.parent_task_id is None
        and isinstance(task.input_data, dict)
        and task.input_data.get("kind") in ("project_run", "default_run")
    )


class AnalyticsService:
    """Computes aggregated statistics for the dashboard."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)

    async def dashboard(
        self,
        *,
        user_id: str | None = None,
        project_id: UUID | None = None,
        days: int = 30,
    ) -> DashboardStats:
        now = datetime.now(UTC)
        since = now - timedelta(days=days)
        tasks = await self.tasks.list_since(
            since=since, user_id=user_id, project_id=project_id
        )
        services = {
            row.id: row.name
            for row in (await self.session.execute(select(Service))).scalars()
        }
        project_ids = {t.project_id for t in tasks if t.project_id}
        projects = {}
        if project_ids:
            rows = await self.session.execute(
                select(Project).where(Project.id.in_(project_ids))
            )
            projects = {p.id: p.name for p in rows.scalars()}

        acc = _Accumulator(
            since=since, days=days, now=now, services=services, projects=projects
        )
        for task in tasks:
            acc.ingest(task)

        return DashboardStats(
            user_id=user_id,
            project_id=project_id,
            since=since,
            generated_at=now,
            total_tasks=len(tasks),
            total_runs=acc.runs,
            runs_failed=acc.runs_failed,
            avg_run_seconds=acc.avg_run_seconds(),
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
            by_service=acc.by_service_stats(),
            by_project=acc.by_project_stats(),
            timeseries=acc.timeseries(),
            alerts=acc.top_alerts(_MAX_ALERTS),
        )


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class _Accumulator:
    """Mutable aggregation state, fed one task at a time."""

    def __init__(
        self,
        *,
        since: datetime,
        days: int,
        now: datetime,
        services: dict[UUID, str] | None = None,
        projects: dict[UUID, str] | None = None,
    ) -> None:
        self._now = now
        self._services = services or {}
        self._projects = projects or {}
        self.runs = 0
        self.runs_failed = 0
        self._run_seconds: list[float] = []
        # service name -> [tasks, errors, [compute seconds]]
        self._service: dict[str, list] = {}
        # project id -> [runs, detections, flagged]
        self._project: dict[UUID, list[int]] = defaultdict(lambda: [0, 0, 0])
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
        self._ingest_timing(task)
        for detection in _iter_detections(task):
            self._ingest_detection(task, detection, created, bucket)

    def _ingest_timing(self, task: Task) -> None:
        """Runs, and what each service spent computing."""
        seconds = _seconds(task)
        if _is_run(task):
            self.runs += 1
            if task.status == TaskStatus.ERROR:
                self.runs_failed += 1
            if seconds is not None:
                self._run_seconds.append(seconds)
            if task.project_id:
                self._project[task.project_id][0] += 1
        name = self._services.get(task.service_id) if task.service_id else None
        if name:
            stat = self._service.setdefault(name, [0, 0, []])
            stat[0] += 1
            if task.status == TaskStatus.ERROR:
                stat[1] += 1
            if seconds is not None:
                stat[2].append(seconds)

    def _ingest_detection(
        self,
        task: Task,
        detection: dict,
        created: datetime,
        bucket: dict[str, int] | None,
    ) -> None:
        self.total_detections += 1
        self._user_detections[task.user_id] += 1
        if task.project_id:
            self._project[task.project_id][1] += 1
        if bucket is not None:
            bucket["detections"] += 1

        dtype = _detection_type(detection)
        self._type_total[dtype] += 1

        if not detection.get("flagged"):
            return

        self.total_flagged += 1
        self._type_flagged[dtype] += 1
        self._user_flagged[task.user_id] += 1
        if task.project_id:
            self._project[task.project_id][2] += 1
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

    def avg_run_seconds(self) -> float:
        return (
            sum(self._run_seconds) / len(self._run_seconds)
            if self._run_seconds
            else 0.0
        )

    def by_service_stats(self) -> list[ServiceStat]:
        """Slowest services first: where the compute time goes."""
        stats = [
            ServiceStat(
                service=name,
                tasks=tasks,
                errors=errors,
                timed=len(times),
                avg_seconds=sum(times) / len(times) if times else 0.0,
                max_seconds=max(times, default=0.0),
                total_seconds=sum(times),
            )
            for name, (tasks, errors, times) in self._service.items()
        ]
        return sorted(stats, key=lambda s: s.total_seconds, reverse=True)

    def by_project_stats(self) -> list[ProjectStat]:
        return sorted(
            (
                ProjectStat(
                    project_id=pid,
                    name=self._projects.get(pid, str(pid)),
                    runs=runs,
                    detections=detections,
                    flagged=flagged,
                )
                for pid, (runs, detections, flagged) in self._project.items()
            ),
            key=lambda p: (p.flagged, p.runs),
            reverse=True,
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
