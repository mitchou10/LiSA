from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import AdminDep, CurrentUserDep, ServiceServiceDep
from app.models.enums import ServiceType
from app.schemas.pagination import Page
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate, service: ServiceServiceDep, _admin: AdminDep
) -> ServiceRead:
    obj = await service.create(payload)
    return ServiceRead.model_validate(obj)


@router.get("", response_model=Page[ServiceRead])
async def list_services(
    service: ServiceServiceDep,
    _user: CurrentUserDep,
    q: Annotated[
        str | None, Query(description="Search by name or description.")
    ] = None,
    type: Annotated[ServiceType | None, Query(description="Filter by type.")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ServiceRead]:
    items, total = await service.list_page(q=q, type_=type, limit=limit, offset=offset)
    return Page(
        items=[ServiceRead.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: UUID, service: ServiceServiceDep, _user: CurrentUserDep
) -> ServiceRead:
    obj = await service.get(service_id)
    return ServiceRead.model_validate(obj)


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: UUID,
    payload: ServiceUpdate,
    service: ServiceServiceDep,
    _admin: AdminDep,
) -> ServiceRead:
    obj = await service.update(service_id, payload)
    return ServiceRead.model_validate(obj)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID, service: ServiceServiceDep, _admin: AdminDep
) -> None:
    await service.delete(service_id)
