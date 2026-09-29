from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import publish_profile_changed
from app.models.detection_profile import DetectionProfile, DetectionProfileVersion
from app.repositories.detection_profile import DetectionProfileRepository
from app.schemas.detection_profile import CONFIG_MODELS, VersionCreate
from app.services.detection_defaults import DEFAULT_PROFILES
from app.services.exceptions import ConflictError, NotFoundError


class DetectionProfileService:
    """Versioned storage of per-service detection settings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DetectionProfileRepository(session)

    async def ensure_defaults(self) -> None:
        """Create missing profiles with their default config as version 1."""
        for key, (name, description, factory) in DEFAULT_PROFILES.items():
            if await self.repo.get_by_key(key) is not None:
                continue
            profile = await self.repo.add(
                DetectionProfile(service_key=key, name=name, description=description)
            )
            self.session.add(
                DetectionProfileVersion(
                    profile_id=profile.id,
                    version=1,
                    config=CONFIG_MODELS[key](**factory()).model_dump(),
                    comment="Initial configuration",
                    created_by="system",
                )
            )
        await self.session.commit()

    async def get_profile(self, service_key: str) -> DetectionProfile:
        profile = await self.repo.get_by_key(service_key)
        if profile is None:
            raise NotFoundError(f"No detection profile for '{service_key}'.")
        return profile

    async def get_active(
        self, service_key: str
    ) -> tuple[DetectionProfile, DetectionProfileVersion]:
        profile = await self.get_profile(service_key)
        latest = await self.repo.latest_version(profile)
        if latest is None:
            raise NotFoundError(f"Profile '{service_key}' has no version.")
        return profile, latest

    async def get_version(
        self, service_key: str, version: int
    ) -> tuple[DetectionProfileVersion, int]:
        """Return the version and the number of the active one."""
        profile, active = await self.get_active(service_key)
        found = await self.repo.get_version(profile, version)
        if found is None:
            raise NotFoundError(f"Version {version} of '{service_key}' not found.")
        return found, active.version

    async def list_versions(
        self, service_key: str, *, limit: int, offset: int
    ) -> tuple[list[DetectionProfileVersion], int, int]:
        profile, active = await self.get_active(service_key)
        items, total = await self.repo.list_versions(
            profile, limit=limit, offset=offset
        )
        return items, total, active.version

    async def create_version(
        self, service_key: str, data: VersionCreate, author: str
    ) -> DetectionProfileVersion:
        """Validate ``data.config`` and store it as the new active version."""
        model = CONFIG_MODELS.get(service_key)
        if model is None:
            raise NotFoundError(f"No detection profile for '{service_key}'.")
        config = model(**data.config).model_dump()
        return await self._append(service_key, config, data.comment, author)

    async def rollback(
        self, service_key: str, version: int, author: str
    ) -> DetectionProfileVersion:
        """Re-activate an old version by copying it as a new latest version."""
        source, _ = await self.get_version(service_key, version)
        return await self._append(
            service_key, dict(source.config), f"Rollback to v{version}", author
        )

    async def _append(
        self, service_key: str, config: dict, comment: str | None, author: str
    ) -> DetectionProfileVersion:
        profile, latest = await self.get_active(service_key)
        version = DetectionProfileVersion(
            profile_id=profile.id,
            version=latest.version + 1,
            config=config,
            comment=comment,
            created_by=author,
        )
        self.session.add(version)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "The profile was modified concurrently; reload and retry."
            ) from exc
        await self.session.refresh(version)
        await publish_profile_changed(service_key, version.version)
        return version
