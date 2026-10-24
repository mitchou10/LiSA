from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from app.api.deps import CurrentUserDep, SessionDep
from app.config import get_settings
from app.schemas.file import FileRead
from app.services.file import FileService

router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()


def get_file_service(session: SessionDep) -> FileService:
    return FileService(session)


FileServiceDep = Depends(get_file_service)


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile, user: CurrentUserDep, service: FileService = FileServiceDep
) -> FileRead:
    """Store an uploaded file in object storage and return its metadata."""
    limit = int(settings.max_upload_mb * 1024 * 1024)
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb:g} MB limit.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file."
        )
    obj = await service.upload(user, file.filename or "file", file.content_type, data)
    return FileRead.model_validate(obj)


@router.get("/{file_id}")
async def get_file(
    file_id: UUID, user: CurrentUserDep, service: FileService = FileServiceDep
) -> FileRead:
    return FileRead.model_validate(await service.get(file_id, user))


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: UUID, user: CurrentUserDep, service: FileService = FileServiceDep
) -> Response:
    """Stream the stored bytes (workers fetch their input through this)."""
    obj, data = await service.read(file_id, user)
    return Response(
        content=data,
        media_type=obj.mime or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(obj.filename)}"
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID, user: CurrentUserDep, service: FileService = FileServiceDep
) -> Response:
    await service.delete(file_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
