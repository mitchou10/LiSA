from sqlalchemy import select

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    model = Service

    async def get_by_name(self, name: str) -> Service | None:
        result = await self.session.execute(select(Service).where(Service.name == name))
        return result.scalars().first()
