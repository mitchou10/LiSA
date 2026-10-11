from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AdminDep, CurrentUserDep, TaskServiceDep
from app.core import storage
from app.models.enums import TaskStatus
from app.schemas.pagination import Page
from app.schemas.task import TaskRead, TaskStatusRead, TaskSubmit, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def submit_task(
    payload: TaskSubmit, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskRead:
    """Submit a new task for execution. Requires authentication."""
    obj = await service.submit(payload)
    return TaskRead.model_validate(obj)


@router.get("", response_model=Page[TaskRead])
async def list_tasks(
    service: TaskServiceDep,
    _user: CurrentUserDep,
    user_id: Annotated[str | None, Query()] = None,
    status: Annotated[TaskStatus | None, Query(description="Filter by status.")] = None,
    service_id: Annotated[UUID | None, Query(description="Filter by service.")] = None,
    project_id: Annotated[UUID | None, Query(description="Filter by project.")] = None,
    roots_only: Annotated[
        bool, Query(description="Only return root tasks (no parent).")
    ] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TaskRead]:
    items, total = await service.list_page(
        user_id=user_id,
        status=status,
        service_id=service_id,
        project_id=project_id,
        roots_only=roots_only,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[TaskRead.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskRead:
    obj = await service.get(task_id)
    return TaskRead.model_validate(obj)


@router.get("/{task_id}/pages/{page_number}/image")
async def get_page_image(
    task_id: UUID, page_number: int, service: TaskServiceDep, user: CurrentUserDep
) -> Response:
    """The screenshot of a page parsed by task ``task_id`` (a parser task).

    Only the key found in the task's own output is read from storage, never a
    key given by the caller, and only for the task's owner or an admin.
    """
    task = await service.get(task_id)
    # Same answer for "missing" and "not yours": do not reveal existence.
    if not (user.is_admin or task.user_id == user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found.")
    pages = (task.output_data or {}).get("pages") or []
    key = next(
        (p.get("s3_key") for p in pages if p.get("page_number") == page_number), None
    )
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found.")
    try:
        data = await storage.get_object(key)
    except storage.ObjectNotFoundError:
        raise HTTPException(
            status.HTTP_410_GONE, "The page image was deleted from storage."
        ) from None
    return Response(
        content=data,
        media_type="image/png",
        # Private to the user, but fine to keep for the session.
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{task_id}/status", response_model=TaskStatusRead)
async def get_task_status(
    task_id: UUID, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskStatusRead:
    """Lightweight endpoint to poll a task's progress."""
    obj = await service.get(task_id)
    return TaskStatusRead.model_validate(obj)


@router.get("/{task_id}/children", response_model=list[TaskRead])
async def get_task_children(
    task_id: UUID, service: TaskServiceDep, _user: CurrentUserDep
) -> list[TaskRead]:
    objs = await service.list_children(task_id)
    return [TaskRead.model_validate(o) for o in objs]


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID, payload: TaskUpdate, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskRead:
    obj = await service.update(task_id, payload)
    return TaskRead.model_validate(obj)


@router.post("/{task_id}/revoke", response_model=TaskRead)
async def revoke_task(
    task_id: UUID, service: TaskServiceDep, _admin: AdminDep
) -> TaskRead:
    obj = await service.revoke(task_id)
    return TaskRead.model_validate(obj)


@router.post("/{task_id}/retry", response_model=TaskRead)
async def retry_task(
    task_id: UUID, service: TaskServiceDep, _admin: AdminDep
) -> TaskRead:
    obj = await service.retry(task_id)
    return TaskRead.model_validate(obj)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, service: TaskServiceDep, _admin: AdminDep) -> None:
    await service.delete(task_id)
