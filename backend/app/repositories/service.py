from sqlalchemy import func, or_, select

from app.models.enums import ServiceType
from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    model = Service

    async def get_by_name(self, name: str) -> Service | None:
        result = await self.session.execute(select(Service).where(Service.name == name))
        return result.scalars().first()

    def _filtered(self, *, q: str | None = None, type_: ServiceType | None = None):
        stmt = select(Service)
        if type_ is not None:
            stmt = stmt.where(Service.type == type_)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(Service.name.ilike(like), Service.description.ilike(like))
            )
        return stmt

    async def list_filtered(
        self,
        *,
        q: str | None = None,
        type_: ServiceType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Service]:
        stmt = (
            self._filtered(q=q, type_=type_)
            .order_by(Service.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self, *, q: str | None = None, type_: ServiceType | None = None
    ) -> int:
        stmt = self._filtered(q=q, type_=type_).subquery()
        result = await self.session.execute(select(func.count()).select_from(stmt))
        return int(result.scalar_one())
