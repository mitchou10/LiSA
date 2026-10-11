from datetime import datetime
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
        project_id: UUID | None = None,
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
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        return stmt

    async def list_filtered(
        self,
        *,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        service_id: UUID | None = None,
        roots_only: bool = False,
        project_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            self._filtered(
                user_id=user_id,
                status=status,
                service_id=service_id,
                roots_only=roots_only,
                project_id=project_id,
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
        project_id: UUID | None = None,
    ) -> int:
        stmt = self._filtered(
            user_id=user_id,
            status=status,
            service_id=service_id,
            roots_only=roots_only,
            project_id=project_id,
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

    async def list_since(
        self,
        *,
        since: datetime,
        user_id: str | None = None,
        project_id: UUID | None = None,
    ) -> list[Task]:
        """Return tasks created at/after ``since``, oldest first.

        Used by the analytics dashboard to aggregate detections over time.
        """
        stmt = select(Task).where(Task.created_at >= since)
        if user_id is not None:
            stmt = stmt.where(Task.user_id == user_id)
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        stmt = stmt.order_by(Task.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
