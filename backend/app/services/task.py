from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import dispatch_task
from app.models.enums import TaskStatus
from app.models.task import Task
from app.repositories.service import ServiceRepository
from app.repositories.task import TaskRepository
from app.schemas.task import TaskSubmit, TaskUpdate
from app.services.exceptions import InvalidStateError, NotFoundError
from app.services.pipeline import CannotFeed, feed
from app.services.privacy import mask_text_fields

# Statuses from which a task can no longer transition.
TERMINAL_STATUSES = {TaskStatus.SUCCESS, TaskStatus.ERROR, TaskStatus.REVOKED}


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(task: Task, now: datetime) -> None:
    """Record when the task started (first running) and when it ended."""
    if task.status == TaskStatus.RUNNING and task.started_at is None:
        task.started_at = now
    if task.status in TERMINAL_STATUSES and task.finished_at is None:
        task.finished_at = now


class TaskService:
    """Business logic for the task lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TaskRepository(session)
        self.services = ServiceRepository(session)

    async def dispatch(
        self, task: Task, input_data: dict[str, Any] | None = None
    ) -> None:
        """Send the task to its service's worker via the broker (best-effort).

        ``input_data`` is what the worker gets when it differs from the stored
        input (private runs store a masked copy).
        """
        if task.service_id is None:
            return
        service = await self.services.get(task.service_id)
        if service is None:
            return
        dispatch_task(
            service.name,
            str(task.id),
            task.input_data if input_data is None else input_data,
            queue=service.queue or service.name,
        )

    async def submit(self, data: TaskSubmit) -> Task:
        if data.parent_task_id is not None:
            parent = await self.repo.get(data.parent_task_id)
            if parent is None:
                raise NotFoundError(f"Parent task {data.parent_task_id} not found.")
        task = Task(
            user_id=data.user_id,
            input_data=data.input_data,
            service_id=data.service_id,
            parent_task_id=data.parent_task_id,
            status=TaskStatus.PENDING,
            progress=0,
        )
        task = await self.repo.add(task)
        await self.session.commit()
        await self.dispatch(task)
        return task

    async def get(self, task_id: UUID) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found.")
        return task

    async def list_all(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        if user_id is not None:
            return await self.repo.list_by_user(user_id, limit=limit, offset=offset)
        return await self.repo.list(limit=limit, offset=offset)

    async def list_page(
        self,
        *,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        service_id: UUID | None = None,
        project_id: UUID | None = None,
        roots_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        """Return a filtered page of tasks together with the total count."""
        items = await self.repo.list_filtered(
            user_id=user_id,
            status=status,
            service_id=service_id,
            project_id=project_id,
            roots_only=roots_only,
            limit=limit,
            offset=offset,
        )
        total = await self.repo.count_filtered(
            user_id=user_id,
            status=status,
            service_id=service_id,
            project_id=project_id,
            roots_only=roots_only,
        )
        return items, total

    async def list_children(self, task_id: UUID) -> list[Task]:
        await self.get(task_id)
        return await self.repo.list_children(task_id)

    async def _is_private(self, task: Task) -> bool:
        """Does the run of this task hide what was found (and not store it)?"""
        if task.parent_task_id is None:
            return False
        parent = await self.repo.get(task.parent_task_id)
        return bool(parent and parent.input_data.get("anonymize"))

    async def update(self, task_id: UUID, data: TaskUpdate) -> Task:
        task = await self.get(task_id)
        changes = data.model_dump(exclude_unset=True)
        private = await self._is_private(task)
        # In a private run the worker's clear output is used (to feed the next
        # workers) but never written: the table only gets the masked copy.
        clear_output = changes.get("output_data") if private else None
        if private:
            for field in ("input_data", "output_data"):
                if changes.get(field) is not None:
                    changes[field] = mask_text_fields(changes[field])
        for field, value in changes.items():
            setattr(task, field, value)
        _stamp(task, _now())
        await self.session.commit()
        await self.session.refresh(task)
        if task.status in TERMINAL_STATUSES:
            await self._release_waiting(task, clear_output, private)
        if task.parent_task_id is not None:
            await self._rollup_parent(task.parent_task_id)
        return task

    async def _release_waiting(
        self,
        task: Task,
        clear_output: dict[str, Any] | None = None,
        private: bool = False,
    ) -> None:
        """Feed the tasks that wait for ``task`` once it is finished.

        Siblings created with ``awaiting`` in their input get what ``feed``
        builds from this task and are dispatched; if it cannot be built (the
        task failed, found nothing), they fail with it.
        """
        if task.parent_task_id is None:
            return
        waiting = [
            t
            for t in await self.repo.list_children(task.parent_task_id)
            if t.status == TaskStatus.PENDING
            and t.input_data.get("awaiting") == str(task.id)
        ]
        released: list[tuple[Task, dict[str, Any]]] = []
        for waiter in waiting:
            try:
                payload = feed(waiter.input_data, task, clear_output)
                # A new dict: JSON columns are not mutation-tracked. A private
                # run stores a masked copy; the worker gets the real payload.
                waiter.input_data = mask_text_fields(payload) if private else payload
                released.append((waiter, payload))
            except CannotFeed as exc:
                waiter.status = TaskStatus.ERROR
                waiter.error = str(exc)
        if not waiting:
            return
        await self.session.commit()
        for waiter, payload in released:
            await self.session.refresh(waiter)
            await self.dispatch(waiter, payload)

    async def _rollup_parent(self, parent_id: UUID) -> None:
        """Recompute a parent task's status/progress from its children.

        A "group" task has no service of its own, so it never runs on a worker.
        Instead its state is derived from its children:

        * progress = mean of children progress
        * status   = success when all children succeed, error if any failed
          (once everything is terminal), running while any child is active,
          else pending.
        """
        parent = await self.repo.get(parent_id)
        if parent is None:
            return
        children = await self.repo.list_children(parent_id)
        if not children:
            return

        statuses = [c.status for c in children]
        progress = round(sum(c.progress for c in children) / len(children))
        all_terminal = all(s in TERMINAL_STATUSES for s in statuses)

        if all_terminal:
            if any(s == TaskStatus.ERROR for s in statuses):
                status = TaskStatus.ERROR
            elif all(s == TaskStatus.REVOKED for s in statuses):
                status = TaskStatus.REVOKED
            else:
                status = TaskStatus.SUCCESS
            progress = 100 if status == TaskStatus.SUCCESS else progress
        elif any(s == TaskStatus.RUNNING for s in statuses) or progress > 0:
            status = TaskStatus.RUNNING
        else:
            status = TaskStatus.PENDING

        # The run's time: from the first worker's start to the last one's end.
        started = min((c.started_at for c in children if c.started_at), default=None)
        finished = (
            max((c.finished_at for c in children if c.finished_at), default=None)
            if all_terminal
            else None
        )

        if (
            parent.status != status
            or parent.progress != progress
            or parent.started_at != started
            or parent.finished_at != finished
        ):
            parent.status = status
            parent.progress = progress
            parent.started_at = started
            parent.finished_at = finished
            await self.session.commit()
            await self.session.refresh(parent)

    async def revoke(self, task_id: UUID) -> Task:
        task = await self.get(task_id)
        if task.status in TERMINAL_STATUSES:
            raise InvalidStateError(
                f"Cannot revoke a task in state '{task.status.value}'."
            )
        task.status = TaskStatus.REVOKED
        _stamp(task, _now())
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def retry(self, task_id: UUID) -> Task:
        task = await self.get(task_id)
        if await self._is_private(task):
            raise InvalidStateError(
                "A task of a private (anonymized) run cannot be retried: its "
                "input was not stored. Start a new run."
            )
        if task.status not in {TaskStatus.ERROR, TaskStatus.REVOKED}:
            raise InvalidStateError(
                "Only failed or revoked tasks can be retried "
                f"(current state: '{task.status.value}')."
            )
        task.status = TaskStatus.PENDING
        task.progress = 0
        task.error = None
        task.output_data = None
        task.started_at = task.finished_at = None
        await self.session.commit()
        await self.session.refresh(task)
        await self.dispatch(task)
        return task

    async def delete(self, task_id: UUID) -> None:
        task = await self.get(task_id)
        if task.status not in TERMINAL_STATUSES:
            raise InvalidStateError(
                "Only finished tasks (success, error or revoked) can be deleted "
                f"(current state: '{task.status.value}')."
            )
        await self.repo.delete(task)
        await self.session.commit()
