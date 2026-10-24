"""Projects and the catalog of what they look for."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    ClassificationDefinition,
    ClassificationLabel,
    EntityDefinition,
    RelationDefinition,
    SafetyDefinition,
    SafetyLabel,
)
from app.models.project import Project
from app.schemas.auth import CurrentUser
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError
from app.services.project_defaults import default_pii_entities, default_safety_checks


@dataclass(frozen=True)
class Kind:
    """One kind of definition: its table, the field naming it, its labels."""

    key: str
    model: type
    name_field: str
    label_model: type | None = None


KINDS: dict[str, Kind] = {
    "classifications": Kind(
        "classifications", ClassificationDefinition, "name", ClassificationLabel
    ),
    "entities": Kind("entities", EntityDefinition, "label"),
    "relations": Kind("relations", RelationDefinition, "name"),
    "safety": Kind("safety", SafetyDefinition, "name", SafetyLabel),
}


def can_access(project: Project, user: CurrentUser) -> bool:
    return user.is_admin or project.created_by == user.id


class ProjectService:
    """Projects, with the same access rule everywhere: owner or admin."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, project_id: UUID, user: CurrentUser) -> Project:
        project = await self.session.get(Project, project_id)
        # Same answer for "missing" and "not yours": do not reveal existence.
        if project is None or not can_access(project, user):
            raise NotFoundError(f"Project {project_id} not found.")
        return project

    async def _name_taken(
        self, owner: str, name: str, *, except_id: UUID | None = None
    ) -> bool:
        stmt = select(Project.id).where(
            Project.created_by == owner, func.lower(Project.name) == name.lower()
        )
        if except_id is not None:
            stmt = stmt.where(Project.id != except_id)
        return (await self.session.execute(stmt)).first() is not None

    async def create(self, user: CurrentUser, data: ProjectCreate) -> Project:
        if await self._name_taken(user.id, data.name):
            raise ConflictError(f"You already have a project named '{data.name}'.")
        project = Project(
            name=data.name, description=data.description, created_by=user.id
        )
        self.session.add(project)
        # Every new project starts guarded out of the box: the default safety
        # checks (prompt safety, jailbreak / prompt injection, toxicity) and the
        # PII entities (names, emails, phone numbers, IDs, secrets...). They
        # are plain catalog rows: edit or delete them like any other
        # definition.
        for payload in default_pii_entities():
            project.entities.append(EntityDefinition(created_by=user.id, **payload))
        for payload in default_safety_checks():
            project.safety_checks.append(
                SafetyDefinition(
                    created_by=user.id,
                    **{k: v for k, v in payload.items() if k not in ("labels",)},
                    labels=[
                        SafetyLabel(name=lb["name"], is_ok=lb["is_ok"], position=pos)
                        for pos, lb in enumerate(payload["labels"])
                    ],
                )
            )
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(
        self, project_id: UUID, user: CurrentUser, data: ProjectUpdate
    ) -> Project:
        project = await self.get(project_id, user)
        changes = data.model_dump(exclude_unset=True)
        name = changes.get("name")
        if name and await self._name_taken(
            project.created_by, name, except_id=project.id
        ):
            raise ConflictError(f"You already have a project named '{name}'.")
        for field, value in changes.items():
            setattr(project, field, value)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: UUID, user: CurrentUser) -> None:
        project = await self.get(project_id, user)
        await self.session.delete(project)
        await self.session.commit()

    async def list_page(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[list[ProjectSummary], int]:
        base = select(Project)
        if not user.is_admin:
            base = base.where(Project.created_by == user.id)
        total = (
            await self.session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        projects = (
            (
                await self.session.execute(
                    base.order_by(Project.created_at.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        counts = {p.id: {} for p in projects}
        for kind in KINDS.values():
            rows = await self.session.execute(
                select(kind.model.project_id, func.count())
                .where(kind.model.project_id.in_(counts))
                .group_by(kind.model.project_id)
            )
            for project_id, n in rows:
                counts[project_id][kind.key] = n
        items = [
            ProjectSummary(
                **ProjectRead.model_validate(p).model_dump(),
                classifications=counts[p.id].get("classifications", 0),
                entities=counts[p.id].get("entities", 0),
                relations=counts[p.id].get("relations", 0),
                safety_checks=counts[p.id].get("safety", 0),
            )
            for p in projects
        ]
        return items, total


class CatalogService:
    """CRUD of one kind of definition inside a project."""

    def __init__(self, session: AsyncSession, projects: ProjectService) -> None:
        self.session = session
        self.projects = projects

    async def _by_name(
        self, kind: Kind, project_id: UUID, name: str, *, except_id: UUID | None = None
    ) -> bool:
        column = getattr(kind.model, kind.name_field)
        stmt = select(kind.model.id).where(
            kind.model.project_id == project_id, func.lower(column) == name.lower()
        )
        if except_id is not None:
            stmt = stmt.where(kind.model.id != except_id)
        return (await self.session.execute(stmt)).first() is not None

    async def list(self, kind: Kind, project_id: UUID, user: CurrentUser) -> list[Any]:
        await self.projects.get(project_id, user)
        column = getattr(kind.model, kind.name_field)
        result = await self.session.execute(
            select(kind.model)
            .where(kind.model.project_id == project_id)
            .order_by(column)
        )
        return list(result.scalars().all())

    async def get(
        self, kind: Kind, project_id: UUID, definition_id: UUID, user: CurrentUser
    ) -> Any:
        await self.projects.get(project_id, user)
        obj = await self.session.get(kind.model, definition_id)
        if obj is None or obj.project_id != project_id:
            raise NotFoundError(
                f"{kind.key[:-1].capitalize()} {definition_id} not found."
            )
        return obj

    @staticmethod
    def _labels(kind: Kind, labels: list[dict[str, Any]]) -> list[Any]:
        rows = []
        for position, label in enumerate(labels):
            fields = {"name": label["name"], "description": label.get("description")}
            if kind.label_model is SafetyLabel:
                fields["is_ok"] = bool(label.get("is_ok"))
            rows.append(kind.label_model(position=position, **fields))
        return rows

    async def create(
        self, kind: Kind, project_id: UUID, user: CurrentUser, data: dict[str, Any]
    ) -> Any:
        await self.projects.get(project_id, user)
        name = data[kind.name_field]
        if await self._by_name(kind, project_id, name):
            raise ConflictError(f"'{name}' already exists in this project.")
        labels = data.pop("labels", None)
        obj = kind.model(project_id=project_id, created_by=user.id, **data)
        if kind.label_model is not None:
            obj.labels = self._labels(kind, labels or [])
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(
        self,
        kind: Kind,
        project_id: UUID,
        definition_id: UUID,
        user: CurrentUser,
        changes: dict[str, Any],
    ) -> Any:
        obj = await self.get(kind, project_id, definition_id, user)
        name = changes.get(kind.name_field)
        if name and await self._by_name(kind, project_id, name, except_id=obj.id):
            raise ConflictError(f"'{name}' already exists in this project.")
        labels = changes.pop("labels", None)
        for field, value in changes.items():
            setattr(obj, field, value)
        if labels is not None and kind.label_model is not None:
            obj.labels = self._labels(kind, labels)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(
        self, kind: Kind, project_id: UUID, definition_id: UUID, user: CurrentUser
    ) -> None:
        obj = await self.get(kind, project_id, definition_id, user)
        await self.session.delete(obj)
        await self.session.commit()
