from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import TaskServiceDep
from app.models.enums import TaskStatus
from app.schemas.pagination import Page
from app.schemas.task import TaskRead, TaskStatusRead, TaskSubmit, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def submit_task(payload: TaskSubmit, service: TaskServiceDep) -> TaskRead:
    """Submit a new task for execution."""
    obj = await service.submit(payload)
    return TaskRead.model_validate(obj)


@router.get("", response_model=Page[TaskRead])
async def list_tasks(
    service: TaskServiceDep,
    user_id: str | None = Query(default=None),
    status: TaskStatus | None = Query(default=None, description="Filter by status."),
    service_id: UUID | None = Query(default=None, description="Filter by service."),
    roots_only: bool = Query(
        default=False, description="Only return root tasks (no parent)."
    ),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[TaskRead]:
    items, total = await service.list_page(
        user_id=user_id,
        status=status,
        service_id=service_id,
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
async def get_task(task_id: UUID, service: TaskServiceDep) -> TaskRead:
    obj = await service.get(task_id)
    return TaskRead.model_validate(obj)


@router.get("/{task_id}/status", response_model=TaskStatusRead)
async def get_task_status(task_id: UUID, service: TaskServiceDep) -> TaskStatusRead:
    """Lightweight endpoint to poll a task's progress."""
    obj = await service.get(task_id)
    return TaskStatusRead.model_validate(obj)


@router.get("/{task_id}/children", response_model=list[TaskRead])
async def get_task_children(task_id: UUID, service: TaskServiceDep) -> list[TaskRead]:
    objs = await service.list_children(task_id)
    return [TaskRead.model_validate(o) for o in objs]


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID, payload: TaskUpdate, service: TaskServiceDep
) -> TaskRead:
    obj = await service.update(task_id, payload)
    return TaskRead.model_validate(obj)


@router.post("/{task_id}/revoke", response_model=TaskRead)
async def revoke_task(task_id: UUID, service: TaskServiceDep) -> TaskRead:
    obj = await service.revoke(task_id)
    return TaskRead.model_validate(obj)


@router.post("/{task_id}/retry", response_model=TaskRead)
async def retry_task(task_id: UUID, service: TaskServiceDep) -> TaskRead:
    obj = await service.retry(task_id)
    return TaskRead.model_validate(obj)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, service: TaskServiceDep) -> None:
    await service.delete(task_id)
