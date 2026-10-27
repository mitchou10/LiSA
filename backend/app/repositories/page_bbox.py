from uuid import UUID

from sqlalchemy import select

from app.models.page_bbox import PageBbox
from app.repositories.base import BaseRepository


class PageBboxRepository(BaseRepository[PageBbox]):
    model = PageBbox

    async def list_for_run(
        self, run_id: UUID, page_number: int | None = None
    ) -> list[PageBbox]:
        stmt = select(PageBbox).where(PageBbox.run_id == run_id)
        if page_number is not None:
            stmt = stmt.where(PageBbox.page_number == page_number)
        stmt = stmt.order_by(PageBbox.page_number, PageBbox.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
