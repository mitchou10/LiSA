from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def _filtered(
        self,
        *,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        service_id: UUID | None = None,
        roots_only: bool = False,
    ):
        stmt = select(Task)
        if user_id is not None:
            stmt = stmt.where(Task.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if service_id is not None:
            stmt = stmt.where(Task.service_id == service_id)
        if roots_only:
            stmt = stmt.where(Task.parent_task_id.is_(None))
        return stmt

    async def list_filtered(
        self,
        *,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        service_id: UUID | None = None,
        roots_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            self._filtered(
                user_id=user_id,
                status=status,
                service_id=service_id,
                roots_only=roots_only,
            )
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        *,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        service_id: UUID | None = None,
        roots_only: bool = False,
    ) -> int:
        stmt = self._filtered(
            user_id=user_id,
            status=status,
            service_id=service_id,
            roots_only=roots_only,
        ).subquery()
        result = await self.session.execute(select(func.count()).select_from(stmt))
        return int(result.scalar_one())

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
