from uuid import UUID

from sqlalchemy import select

from app.models.box_override import BoxOverride
from app.models.text_replacement import TextReplacement
from app.repositories.base import BaseRepository


class TextReplacementRepository(BaseRepository[TextReplacement]):
    model = TextReplacement

    async def list_for_run(self, run_id: UUID) -> list[TextReplacement]:
        result = await self.session.execute(
            select(TextReplacement)
            .where(TextReplacement.run_id == run_id)
            .order_by(TextReplacement.key)
        )
        return list(result.scalars().all())

    async def find(self, run_id: UUID, key: str) -> TextReplacement | None:
        result = await self.session.execute(
            select(TextReplacement).where(
                TextReplacement.run_id == run_id, TextReplacement.key == key
            )
        )
        return result.scalar_one_or_none()


class BoxOverrideRepository(BaseRepository[BoxOverride]):
    model = BoxOverride

    async def list_for_run(self, run_id: UUID) -> list[BoxOverride]:
        result = await self.session.execute(
            select(BoxOverride)
            .where(BoxOverride.run_id == run_id)
            .order_by(BoxOverride.page_number, BoxOverride.entity_id)
        )
        return list(result.scalars().all())

    async def find(
        self, run_id: UUID, page_number: int, entity_id: str, bbox_index: int
    ) -> BoxOverride | None:
        result = await self.session.execute(
            select(BoxOverride).where(
                BoxOverride.run_id == run_id,
                BoxOverride.page_number == page_number,
                BoxOverride.entity_id == entity_id,
                BoxOverride.bbox_index == bbox_index,
            )
        )
        return result.scalar_one_or_none()
