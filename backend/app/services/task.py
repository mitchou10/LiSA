from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
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
        # NOTE: this is where the task would be dispatched to the broker.
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

    async def list_children(self, task_id: UUID) -> list[Task]:
        await self.get(task_id)
        return await self.repo.list_children(task_id)

    async def update(self, task_id: UUID, data: TaskUpdate) -> Task:
        task = await self.get(task_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        await self.session.commit()
        await self.session.refresh(task)
        return task

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
        # NOTE: re-dispatch to the broker here.
        return task

    async def delete(self, task_id: UUID) -> None:
        task = await self.get(task_id)
        await self.repo.delete(task)
        await self.session.commit()
