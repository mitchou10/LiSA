from app.models.file import StoredFile
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[StoredFile]):
    model = StoredFile
