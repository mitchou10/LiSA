from sqlalchemy import func, select

from app.models.detection_profile import DetectionProfile, DetectionProfileVersion
from app.repositories.base import BaseRepository


class DetectionProfileRepository(BaseRepository[DetectionProfile]):
    model = DetectionProfile

    async def get_by_key(self, service_key: str) -> DetectionProfile | None:
        result = await self.session.execute(
            select(DetectionProfile).where(DetectionProfile.service_key == service_key)
        )
        return result.scalars().first()

    async def latest_version(
        self, profile: DetectionProfile
    ) -> DetectionProfileVersion | None:
        result = await self.session.execute(
            select(DetectionProfileVersion)
            .where(DetectionProfileVersion.profile_id == profile.id)
            .order_by(DetectionProfileVersion.version.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_version(
        self, profile: DetectionProfile, version: int
    ) -> DetectionProfileVersion | None:
        result = await self.session.execute(
            select(DetectionProfileVersion).where(
                DetectionProfileVersion.profile_id == profile.id,
                DetectionProfileVersion.version == version,
            )
        )
        return result.scalars().first()

    async def list_versions(
        self, profile: DetectionProfile, *, limit: int, offset: int
    ) -> tuple[list[DetectionProfileVersion], int]:
        base = select(DetectionProfileVersion).where(
            DetectionProfileVersion.profile_id == profile.id
        )
        result = await self.session.execute(
            base.order_by(DetectionProfileVersion.version.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        return list(result.scalars().all()), int(total.scalar_one())
