from __future__ import annotations

import hashlib
import logging
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.file import StoredFile
from app.repositories.file import FileRepository
from app.schemas.auth import CurrentUser
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class FileService:
    """Upload, read and delete user files kept in object storage."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FileRepository(session)

    async def upload(
        self, owner: CurrentUser, filename: str, mime: str | None, data: bytes
    ) -> StoredFile:
        file_id = uuid.uuid4()
        # No user-supplied text in the key: the original name lives in the DB.
        key = f"uploads/{file_id}"
        await storage.put_object(key, data, mime or "application/octet-stream")
        obj = StoredFile(
            id=file_id,
            owner_id=owner.id,
            filename=filename,
            mime=mime,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            storage_key=key,
        )
        try:
            obj = await self.repo.add(obj)
            await self.session.commit()
        except Exception:
            await self._discard(key)
            raise
        return obj

    async def get(self, file_id: UUID, user: CurrentUser) -> StoredFile:
        obj = await self.repo.get(file_id)
        # Same answer for "missing" and "not yours": do not reveal existence.
        if obj is None or not self._can_access(obj, user):
            raise NotFoundError(f"File {file_id} not found.")
        return obj

    async def read(self, file_id: UUID, user: CurrentUser) -> tuple[StoredFile, bytes]:
        obj = await self.get(file_id, user)
        return obj, await storage.get_object(obj.storage_key)

    async def delete(self, file_id: UUID, user: CurrentUser) -> None:
        obj = await self.get(file_id, user)
        key = obj.storage_key
        await self.repo.delete(obj)
        await self.session.commit()
        await self._discard(key)

    @staticmethod
    def _can_access(obj: StoredFile, user: CurrentUser) -> bool:
        return user.is_admin or obj.owner_id == user.id

    @staticmethod
    async def _discard(key: str) -> None:
        """Best effort: a storage failure must not undo the database change."""
        try:
            await storage.delete_object(key)
        except Exception:
            logger.exception("Could not delete object %s from storage", key)
