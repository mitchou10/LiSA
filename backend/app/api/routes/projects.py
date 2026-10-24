"""Projects, and the classifications / entities / relations / safety checks
each project looks for."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pagination import Page
from app.schemas.project import (
    ClassificationCreate,
    ClassificationRead,
    ClassificationUpdate,
    EntityCreate,
    EntityRead,
    EntityUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    RelationCreate,
    RelationRead,
    RelationUpdate,
    SafetyCreate,
    SafetyRead,
    SafetyUpdate,
)
from app.schemas.run import RunCreate, RunRead
from app.services.project import KINDS, CatalogService, ProjectService
from app.services.run import RunService

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(session: SessionDep) -> ProjectService:
    return ProjectService(session)


def get_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(session, ProjectService(session))


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


# -- projects ---------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, service: ProjectServiceDep, user: CurrentUserDep
) -> ProjectRead:
    return ProjectRead.model_validate(await service.create(user, payload))


@router.get("")
async def list_projects(
    service: ProjectServiceDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProjectSummary]:
    """Your projects (all of them for an admin), with their counts."""
    items, total = await service.list_page(user, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{project_id}")
async def get_project(
    project_id: UUID, service: ProjectServiceDep, user: CurrentUserDep
) -> ProjectRead:
    return ProjectRead.model_validate(await service.get(project_id, user))


@router.patch("/{project_id}")
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    service: ProjectServiceDep,
    user: CurrentUserDep,
) -> ProjectRead:
    return ProjectRead.model_validate(await service.update(project_id, user, payload))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, service: ProjectServiceDep, user: CurrentUserDep
) -> Response:
    await service.delete(project_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- runs -------------------------------------------------------------------------------
@router.post("/{project_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_run(
    project_id: UUID, payload: RunCreate, session: SessionDep, user: CurrentUserDep
) -> RunRead:
    """Analyse a text or files with what the project looks for.

    Returns the run: a parent task whose children are the workers, in order.
    Poll ``GET /tasks/{id}`` and ``GET /tasks/{id}/children``.
    """
    return await RunService(session).start(project_id, user, payload)


# -- the four kinds of definitions ----------------------------------------------------
def _register(kind_key, create_model, update_model, read_model) -> None:
    """The same five routes for each kind, under /projects/{id}/<kind>."""
    kind = KINDS[kind_key]
    path = f"/{{project_id}}/{kind_key}"

    @router.get(path, response_model=list[read_model], name=f"list_{kind_key}")
    async def list_definitions(
        project_id: UUID, service: CatalogServiceDep, user: CurrentUserDep
    ):
        return await service.list(kind, project_id, user)

    @router.post(
        path,
        response_model=read_model,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{kind_key}",
    )
    async def create_definition(
        project_id: UUID,
        payload: create_model,
        service: CatalogServiceDep,
        user: CurrentUserDep,
    ):
        return await service.create(kind, project_id, user, payload.model_dump())

    @router.get(
        f"{path}/{{definition_id}}", response_model=read_model, name=f"get_{kind_key}"
    )
    async def get_definition(
        project_id: UUID,
        definition_id: UUID,
        service: CatalogServiceDep,
        user: CurrentUserDep,
    ):
        return await service.get(kind, project_id, definition_id, user)

    @router.patch(
        f"{path}/{{definition_id}}",
        response_model=read_model,
        name=f"update_{kind_key}",
    )
    async def update_definition(
        project_id: UUID,
        definition_id: UUID,
        payload: update_model,
        service: CatalogServiceDep,
        user: CurrentUserDep,
    ):
        return await service.update(
            kind,
            project_id,
            definition_id,
            user,
            payload.model_dump(exclude_unset=True),
        )

    @router.delete(
        f"{path}/{{definition_id}}",
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{kind_key}",
    )
    async def delete_definition(
        project_id: UUID,
        definition_id: UUID,
        service: CatalogServiceDep,
        user: CurrentUserDep,
    ):
        await service.delete(kind, project_id, definition_id, user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


_register(
    "classifications", ClassificationCreate, ClassificationUpdate, ClassificationRead
)
_register("entities", EntityCreate, EntityUpdate, EntityRead)
_register("relations", RelationCreate, RelationUpdate, RelationRead)
_register("safety", SafetyCreate, SafetyUpdate, SafetyRead)
