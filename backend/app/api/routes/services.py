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
    q: str | None = Query(default=None, description="Search by name or description."),
    type: ServiceType | None = Query(default=None, description="Filter by type."),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
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
