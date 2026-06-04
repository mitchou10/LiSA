from uuid import UUID

from sqlalchemy import select

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def list_by_user(
        self, user_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_children(self, parent_task_id: UUID) -> list[Task]:
        result = await self.session.execute(
            select(Task).where(Task.parent_task_id == parent_task_id)
        )
        return list(result.scalars().all())
