"""Purge the content of finished runs, keep what the statistics are made of.

A purge removes what the documents said, from the database and from storage:

* the texts, contents and file names in every task of the run (masked with
  ``*``, same length), and the page images in storage;
* the replacement texts and corrected boxes users set on the run.

Task rows, services, durations, statuses, labels, scores, offsets, boxes and
the boxes users drew stay: the dashboard keeps counting them. The anonymized
text a run produced is not what the documents said, so it stays too.

It runs on request, with an export, and on its own once a run is older than
``retention_days``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import storage
from app.models.box_override import BoxOverride
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.text_replacement import TextReplacement
from app.repositories.service import ServiceRepository
from app.repositories.task import TaskRepository
from app.services.privacy import mask, purge_content, storage_keys
from app.services.run import ANONYMIZE

logger = logging.getLogger(__name__)

_TERMINAL = (TaskStatus.SUCCESS, TaskStatus.ERROR, TaskStatus.REVOKED)
_RUN_KINDS = ("project_run", "default_run")


class PurgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.services = ServiceRepository(session)

    async def purge_run(self, run_id: UUID) -> datetime | None:
        """Purge a run's content. Returns when it was purged (None: not found).

        Safe to repeat: a run already purged is left as it is.
        """
        run = await self.tasks.get(run_id)
        if run is None or run.parent_task_id is not None:
            return None
        if run.purged_at is not None:
            return run.purged_at

        children = await self.tasks.list_children(run.id)
        keys: set[str] = set()
        for task in [run, *children]:
            keys |= storage_keys(task.input_data) | storage_keys(task.output_data)
            task.input_data = purge_content(task.input_data)
            if not await self._is_anonymize(task):
                task.output_data = purge_content(task.output_data)
            if task.error:
                task.error = mask(task.error)
        for model in (TextReplacement, BoxOverride):
            await self.session.execute(delete(model).where(model.run_id == run.id))
        run.purged_at = datetime.now(UTC)
        purged_at = run.purged_at
        await self.session.commit()
        for key in keys:
            await self._discard(key)
        return purged_at

    async def purge_expired(self, now: datetime | None = None) -> int:
        """Purge every finished run older than ``retention_days``. Returns how many."""
        days = get_settings().retention_days
        if days <= 0:
            return 0
        cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
        stmt = select(Task).where(
            Task.parent_task_id.is_(None),
            Task.purged_at.is_(None),
            Task.status.in_(_TERMINAL),
        )
        count = 0
        for run in (await self.session.execute(stmt)).scalars().all():
            if (run.input_data or {}).get("kind") not in _RUN_KINDS:
                continue
            ended = run.finished_at or run.created_at
            if ended.tzinfo is None:
                ended = ended.replace(tzinfo=UTC)
            if ended < cutoff and await self.purge_run(run.id):
                count += 1
        return count

    async def _is_anonymize(self, task: Task) -> bool:
        if task.service_id is None:
            return False
        service = await self.services.get(task.service_id)
        return service is not None and service.name == ANONYMIZE

    @staticmethod
    async def _discard(key: str) -> None:
        """Best effort: a storage failure must not undo the database change."""
        try:
            await storage.delete_object(key)
        except Exception:
            logger.exception("Could not delete object %s from storage", key)


async def purge_loop(session_factory) -> None:
    """Purge the runs past their retention, now and then, until cancelled."""
    interval = max(60, get_settings().purge_interval_seconds)
    while True:
        try:
            async with session_factory() as session:
                purged = await PurgeService(session).purge_expired()
            if purged:
                logger.info("Purged the content of %d expired run(s)", purged)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Purge of expired runs failed")
        await asyncio.sleep(interval)
