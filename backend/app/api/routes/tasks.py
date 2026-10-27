from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AdminDep, CurrentUserDep, SessionDep, TaskServiceDep
from app.core import storage
from app.models.box_override import BoxOverride
from app.models.enums import TaskStatus
from app.models.page_bbox import PageBbox
from app.models.text_replacement import TextReplacement, replacement_key
from app.repositories.page_bbox import PageBboxRepository
from app.repositories.run_edit import BoxOverrideRepository, TextReplacementRepository
from app.schemas.auth import CurrentUser
from app.schemas.page_bbox import BoxGeometry, PageBboxCreate, PageBboxRead
from app.schemas.pagination import Page
from app.schemas.render import RenderRequest
from app.schemas.retention import PurgeRead
from app.schemas.run import DefaultRunCreate, RunRead
from app.schemas.run_edit import (
    BoxOverrideRead,
    BoxOverrideSet,
    ReplacementRead,
    ReplacementSet,
)
from app.schemas.task import TaskRead, TaskStatusRead, TaskSubmit, TaskUpdate
from app.services.purge import PurgeService
from app.services.render import RenderError, RenderService
from app.services.run import RunService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def check_if_admin_or_owner(_user: CurrentUser, obj: TaskRead) -> TaskRead:
    if not (_user.is_admin or obj.user_id == _user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    return obj


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_task(
    payload: TaskSubmit, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskRead:
    """Submit a new task for execution. Requires authentication."""
    obj = await service.submit(payload)
    return TaskRead.model_validate(obj)


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def start_default_run(
    payload: DefaultRunCreate, session: SessionDep, user: CurrentUserDep
) -> RunRead:
    """Analyse a text or files with the default definitions, no project.

    Applies the same defaults every new project is seeded with: the PII
    entities (ner) and the safety checks. Returns the run like a project run.
    """
    return await RunService(session).start_default(user, payload)


@router.get("/me")
async def list_my_tasks(
    service: TaskServiceDep,
    user: CurrentUserDep,
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
        user_id=user.id,
        status=status,
        service_id=service_id,
        project_id=project_id,
        roots_only=roots_only,
        limit=limit,
        offset=offset,
    )
    return Page[TaskRead](
        items=[TaskRead.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("")
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
    if not _user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized.")
    items, total = await service.list_page(
        user_id=user_id,
        status=status,
        service_id=service_id,
        project_id=project_id,
        roots_only=roots_only,
        limit=limit,
        offset=offset,
    )
    return Page[TaskRead](
        items=[TaskRead.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}")
async def get_task(
    task_id: UUID, service: TaskServiceDep, _user: CurrentUserDep
) -> TaskRead:
    obj = await service.get(task_id)
    return check_if_admin_or_owner(_user, TaskRead.model_validate(obj))


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


@router.post("/{task_id}/render")
async def render_run_pages(
    task_id: UUID,
    payload: RenderRequest,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> Response:
    """The pages of a finished file run, blurred and annotated, as a download.

    ``task_id`` is the run (the parent task). The pages come from the run's
    own tasks, never from anything the caller sends, and only for the run's
    owner or an admin. ``format`` picks the file: one PNG (one page), a ZIP of
    PNGs, or a PDF; ``blur`` picks what to hide (nothing, the selected
    entities, or the whole page); ``boxes`` draws each kept entity's box with
    its label above it.
    """
    task = await service.get(task_id)
    # Same answer for "missing" and "not yours": do not reveal existence.
    if not (user.is_admin or task.user_id == user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nothing to render.")
    try:
        rendered = await RenderService(session).render(task_id, payload)
    except RenderError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    if payload.purge_after:
        await PurgeService(session).purge_run(task_id)
    return Response(
        content=rendered.data,
        media_type=rendered.media_type,
        headers={"Content-Disposition": f'attachment; filename="{rendered.filename}"'},
    )


async def _own_run(service: TaskServiceDep, user: CurrentUser, run_id: UUID) -> None:
    """404 unless the run is the caller's (or the caller is an admin)."""
    task = await service.get(run_id)
    if not (user.is_admin or task.user_id == user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")


@router.post("/{task_id}/purge", response_model=PurgeRead)
async def purge_run_content(
    task_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> PurgeRead:
    """Purge what a run's documents said: texts, entities, page images.

    The statistics stay (labels, scores, counts, durations). Cannot be undone.
    """
    await _own_run(service, user, task_id)
    purged_at = await PurgeService(session).purge_run(task_id)
    if purged_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found.")
    return PurgeRead(purged_at=purged_at)


@router.get("/{task_id}/bboxes", response_model=list[PageBboxRead])
async def list_page_bboxes(
    task_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
    page_number: Annotated[int | None, Query(ge=1)] = None,
) -> list[PageBbox]:
    """The boxes drawn on the pages of a run (one page, or all of them)."""
    await _own_run(service, user, task_id)
    return await PageBboxRepository(session).list_for_run(task_id, page_number)


@router.post(
    "/{task_id}/bboxes",
    response_model=PageBboxRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_page_bbox(
    task_id: UUID,
    payload: PageBboxCreate,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> PageBbox:
    """Draw a box on a page: it is blurred on export and kept for the metrics."""
    await _own_run(service, user, task_id)
    bbox = await PageBboxRepository(session).add(
        PageBbox(run_id=task_id, created_by=user.id, **payload.model_dump())
    )
    await session.commit()
    return bbox


@router.delete("/{task_id}/bboxes/{bbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page_bbox(
    task_id: UUID,
    bbox_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> None:
    await _own_run(service, user, task_id)
    repo = PageBboxRepository(session)
    bbox = await repo.get(bbox_id)
    if bbox is None or bbox.run_id != task_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Box not found.")
    await repo.delete(bbox)
    await session.commit()


@router.patch("/{task_id}/bboxes/{bbox_id}", response_model=PageBboxRead)
async def move_page_bbox(
    task_id: UUID,
    bbox_id: UUID,
    payload: BoxGeometry,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> PageBbox:
    """Move or resize a box drawn on a page."""
    await _own_run(service, user, task_id)
    bbox = await PageBboxRepository(session).get(bbox_id)
    if bbox is None or bbox.run_id != task_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Box not found.")
    for name, value in payload.model_dump().items():
        setattr(bbox, name, value)
    await session.commit()
    await session.refresh(bbox)
    return bbox


@router.get("/{task_id}/replacements", response_model=list[ReplacementRead])
async def list_replacements(
    task_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> list[TextReplacement]:
    """The texts to write instead of the entities that read the same."""
    await _own_run(service, user, task_id)
    return await TextReplacementRepository(session).list_for_run(task_id)


@router.put("/{task_id}/replacements", response_model=ReplacementRead)
async def set_replacement(
    task_id: UUID,
    payload: ReplacementSet,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> ReplacementRead:
    """Set (or, when empty, remove) the replacement of every entity reading ``text``."""
    await _own_run(service, user, task_id)
    repo = TextReplacementRepository(session)
    key = replacement_key(payload.text)
    row = await repo.find(task_id, key)
    value = payload.replacement.strip()
    if not value:
        if row is not None:
            await repo.delete(row)
    elif row is None:
        await repo.add(
            TextReplacement(
                run_id=task_id, key=key, replacement=value, created_by=user.id
            )
        )
    else:
        row.replacement = value
    await session.commit()
    return ReplacementRead(key=key, replacement=value)


@router.get("/{task_id}/box-overrides", response_model=list[BoxOverrideRead])
async def list_box_overrides(
    task_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> list[BoxOverride]:
    """The corrected boxes of the detected entities of a run."""
    await _own_run(service, user, task_id)
    return await BoxOverrideRepository(session).list_for_run(task_id)


@router.put("/{task_id}/box-overrides", response_model=BoxOverrideRead)
async def set_box_override(
    task_id: UUID,
    payload: BoxOverrideSet,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> BoxOverride:
    """Correct one box of a detected entity (the detection itself is kept)."""
    await _own_run(service, user, task_id)
    repo = BoxOverrideRepository(session)
    row = await repo.find(
        task_id, payload.page_number, payload.entity_id, payload.bbox_index
    )
    if row is None:
        row = await repo.add(
            BoxOverride(run_id=task_id, created_by=user.id, **payload.model_dump())
        )
    else:
        for name in ("x", "y", "width", "height"):
            setattr(row, name, getattr(payload, name))
    await session.commit()
    await session.refresh(row)
    return row


@router.delete(
    "/{task_id}/box-overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_box_override(
    task_id: UUID,
    override_id: UUID,
    service: TaskServiceDep,
    session: SessionDep,
    user: CurrentUserDep,
) -> None:
    """Put a corrected box back to what was detected."""
    await _own_run(service, user, task_id)
    repo = BoxOverrideRepository(session)
    row = await repo.get(override_id)
    if row is None or row.run_id != task_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Box not found.")
    await repo.delete(row)
    await session.commit()


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
