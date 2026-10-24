from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.api.deps import AdminDep, CurrentUserDep, DetectionProfileServiceDep
from app.schemas.detection_profile import ProfileRead, VersionCreate, VersionRead
from app.schemas.pagination import Page

router = APIRouter(prefix="/detection-profiles", tags=["detection-profiles"])


def _version(obj, active: int) -> VersionRead:
    read = VersionRead.model_validate(obj)
    read.is_active = obj.version == active
    return read


@router.get("/{service_key}")
async def get_profile(
    service_key: str, service: DetectionProfileServiceDep, _user: CurrentUserDep
) -> ProfileRead:
    profile, active = await service.get_active(service_key)
    return ProfileRead(
        service_key=profile.service_key,
        name=profile.name,
        description=profile.description,
        active=_version(active, active.version),
        updated_at=active.created_at,
    )


@router.get("/{service_key}/versions")
async def list_versions(
    service_key: str,
    service: DetectionProfileServiceDep,
    _user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[VersionRead]:
    items, total, active = await service.list_versions(
        service_key, limit=limit, offset=offset
    )
    return Page[VersionRead](
        items=[_version(o, active) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{service_key}/versions/{version}")
async def get_version(
    service_key: str,
    version: int,
    service: DetectionProfileServiceDep,
    _user: CurrentUserDep,
) -> VersionRead:
    obj, active = await service.get_version(service_key, version)
    return _version(obj, active)


@router.post(
    "/{service_key}/versions",
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    service_key: str,
    payload: VersionCreate,
    service: DetectionProfileServiceDep,
    admin: AdminDep,
) -> VersionRead:
    try:
        obj = await service.create_version(service_key, payload, admin.username)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc
    return _version(obj, obj.version)


@router.post(
    "/{service_key}/versions/{version}/activate",
    status_code=status.HTTP_201_CREATED,
)
async def activate_version(
    service_key: str,
    version: int,
    service: DetectionProfileServiceDep,
    admin: AdminDep,
) -> VersionRead:
    obj = await service.rollback(service_key, version, admin.username)
    return _version(obj, obj.version)
