from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import ServiceServiceDep
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate, service: ServiceServiceDep
) -> ServiceRead:
    obj = await service.create(payload)
    return ServiceRead.model_validate(obj)


@router.get("", response_model=list[ServiceRead])
async def list_services(
    service: ServiceServiceDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ServiceRead]:
    objs = await service.list(limit=limit, offset=offset)
    return [ServiceRead.model_validate(o) for o in objs]


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(service_id: UUID, service: ServiceServiceDep) -> ServiceRead:
    obj = await service.get(service_id)
    return ServiceRead.model_validate(obj)


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: UUID, payload: ServiceUpdate, service: ServiceServiceDep
) -> ServiceRead:
    obj = await service.update(service_id, payload)
    return ServiceRead.model_validate(obj)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service_id: UUID, service: ServiceServiceDep) -> None:
    await service.delete(service_id)
