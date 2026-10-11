from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import dispatch_task
from app.models.enums import TaskStatus
from app.models.task import Task
from app.repositories.service import ServiceRepository
from app.repositories.task import TaskRepository
from app.schemas.task import TaskSubmit, TaskUpdate
from app.services.exceptions import InvalidStateError, NotFoundError

# Statuses from which a task can no longer transition.
TERMINAL_STATUSES = {TaskStatus.SUCCESS, TaskStatus.ERROR, TaskStatus.REVOKED}


class TaskService:
    """Business logic for the task lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TaskRepository(session)
        self.services = ServiceRepository(session)

    async def dispatch(self, task: Task) -> None:
        """Send the task to its service's worker via the broker (best-effort)."""
        if task.service_id is None:
            return
        service = await self.services.get(task.service_id)
        if service is None:
            return
        dispatch_task(
            service.name,
            str(task.id),
            task.input_data,
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

    async def update(self, task_id: UUID, data: TaskUpdate) -> Task:
        task = await self.get(task_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        await self.session.commit()
        await self.session.refresh(task)
        if task.status in TERMINAL_STATUSES:
            await self._release_waiting(task)
        if task.parent_task_id is not None:
            await self._rollup_parent(task.parent_task_id)
        return task

    async def _release_waiting(self, task: Task) -> None:
        """Feed the tasks that wait for ``task`` (a parser) once it is finished.

        Sibling tasks created with ``awaiting`` in their input get the pages the
        task produced and are dispatched; if it failed, they fail with it.
        """
        if task.parent_task_id is None:
            return
        waiting = [
            t
            for t in await self.repo.list_children(task.parent_task_id)
            if t.status == TaskStatus.PENDING
            and t.input_data.get("awaiting") == str(task.id)
        ]
        if not waiting:
            return
        pages = (task.output_data or {}).get("pages")
        succeeded = task.status == TaskStatus.SUCCESS and bool(pages)
        for waiter in waiting:
            if succeeded:
                payload = {
                    k: v for k, v in waiter.input_data.items() if k != "awaiting"
                }
                payload["pages"] = pages
                waiter.input_data = (
                    payload  # a new dict: JSON columns are not mutation-tracked
                )
            else:
                waiter.status = TaskStatus.ERROR
                waiter.error = (
                    "The parser found no page."
                    if task.status == TaskStatus.SUCCESS
                    else f"The parser did not finish ({task.status.value}): {task.error or 'no details'}"
                )
        await self.session.commit()
        for waiter in waiting:
            if succeeded:
                await self.session.refresh(waiter)
                await self.dispatch(waiter)

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

        if parent.status != status or parent.progress != progress:
            parent.status = status
            parent.progress = progress
            await self.session.commit()
            await self.session.refresh(parent)

    async def revoke(self, task_id: UUID) -> Task:
        task = await self.get(task_id)
        if task.status in TERMINAL_STATUSES:
            raise InvalidStateError(
                f"Cannot revoke a task in state '{task.status.value}'."
            )
        task.status = TaskStatus.REVOKED
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def retry(self, task_id: UUID) -> Task:
        task = await self.get(task_id)
        if task.status not in {TaskStatus.ERROR, TaskStatus.REVOKED}:
            raise InvalidStateError(
                "Only failed or revoked tasks can be retried "
                f"(current state: '{task.status.value}')."
            )
        task.status = TaskStatus.PENDING
        task.progress = 0
        task.error = None
        task.output_data = None
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
