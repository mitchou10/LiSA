from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ServiceType
from app.models.service import Service
from app.repositories.service import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.exceptions import ConflictError, NotFoundError


class ServiceService:
    """Business logic for managing services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ServiceRepository(session)

    async def create(self, data: ServiceCreate) -> Service:
        existing = await self.repo.get_by_name(data.name)
        if existing is not None:
            raise ConflictError(f"Service '{data.name}' already exists.")
        service = Service(**data.model_dump())
        service = await self.repo.add(service)
        await self.session.commit()
        return service

    async def get(self, service_id: UUID) -> Service:
        service = await self.repo.get(service_id)
        if service is None:
            raise NotFoundError(f"Service {service_id} not found.")
        return service

    async def list(
        self, *, name: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Service]:
        if name is not None:
            service = await self.repo.get_by_name(name)
            return [service] if service is not None else []
        return await self.repo.list(limit=limit, offset=offset)

    async def list_page(
        self,
        *,
        q: str | None = None,
        type_: ServiceType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Service], int]:
        """Return a filtered page of services together with the total count."""
        items = await self.repo.list_filtered(
            q=q, type_=type_, limit=limit, offset=offset
        )
        total = await self.repo.count_filtered(q=q, type_=type_)
        return items, total

    async def update(self, service_id: UUID, data: ServiceUpdate) -> Service:
        service = await self.get(service_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(service, field, value)
        await self.session.commit()
        await self.session.refresh(service)
        return service

    async def delete(self, service_id: UUID) -> None:
        service = await self.get(service_id)
        await self.repo.delete(service)
        await self.session.commit()
