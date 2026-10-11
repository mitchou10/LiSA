"""Run a project's analyses: text or files in, the right workers fed in order.

A run is a parent task (no service of its own) with one child task per worker:

* a **text** becomes pages and goes straight to the analysis workers;
* **files** go to the parser first. The analysis tasks are created at once but
  wait (``awaiting`` in their input) until the parser succeeds: its pages are
  then injected and they are dispatched (see ``TaskService.update``).

Every analysis worker gets only what the user selected in the project.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.file import StoredFile
from app.models.project import Project
from app.models.service import Service
from app.models.task import Task
from app.repositories.service import ServiceRepository
from app.schemas.auth import CurrentUser
from app.schemas.run import RunCreate, RunRead, RunStep
from app.services.exceptions import ConflictError, NotFoundError
from app.services.privacy import mask_text_fields
from app.services.project import KINDS, ProjectService
from app.services.task import TaskService

PARSER = "liteparse-ocr"
ANONYMIZE = "anonymize-v2"

# kind of definition -> (step name, service name, RunCreate field)
ANALYSES = {
    "entities": ("ner", "ner", "entity_ids"),
    "relations": ("relation", "relation", "relation_ids"),
    "classifications": ("classification", "classification", "classification_ids"),
    "safety": ("safety", "safety", "safety_ids"),
}


def text_to_pages(text: str) -> list[dict[str, Any]]:
    """One page per form feed (a page break in extracted text), else one page."""
    parts = [p for p in text.split("\f") if p.strip()] or [text]
    return [{"page_number": i + 1, "content": part} for i, part in enumerate(parts)]


def _labels(definition: Any) -> list[dict[str, Any]]:
    return [
        {"name": lb.name, "description": lb.description} for lb in definition.labels
    ]


def build_inputs(kind: str, definitions: list[Any]) -> dict[str, Any]:
    """The part of a worker's input that comes from the project (no pages)."""
    if kind == "entities":
        return {
            "entities": [
                {
                    "label": d.label,
                    "description": d.description,
                    "category": d.category,
                    "severity": d.severity.value,
                    "action": d.action.value,
                    "threshold": d.threshold,
                    "enabled": d.enabled,
                }
                for d in definitions
            ]
        }
    if kind == "relations":
        return {
            "relations": [
                {"name": d.name, "description": d.description, "threshold": d.threshold}
                for d in definitions
            ]
        }
    if kind == "classifications":
        return {
            "classifications": [
                {
                    "name": d.name,
                    "labels": _labels(d),
                    "multi_label": d.multi_label,
                    "threshold": d.threshold,
                }
                for d in definitions
            ]
        }
    # safety. PII is the ner step's job here, so the safety worker skips it.
    return {
        "pii_labels": [],
        "safety_tasks": [
            {
                "name": d.name,
                "labels": _labels(d),
                "ok_labels": [lb.name for lb in d.labels if lb.is_ok],
                "multi_label": d.multi_label,
                "threshold": d.threshold,
            }
            for d in definitions
        ],
    }


class RunService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectService(session)
        self.tasks = TaskService(session)
        self.services = ServiceRepository(session)

    async def _definitions(
        self, project: Project, kind: str, ids: list[UUID] | None
    ) -> list[Any]:
        """The selected definitions: all enabled ones, or exactly ``ids``."""
        model = KINDS[kind].model
        stmt = select(model).where(model.project_id == project.id)
        if ids is None:
            stmt = stmt.where(model.enabled.is_(True))
        else:
            stmt = stmt.where(model.id.in_(ids))
        found = list((await self.session.execute(stmt)).scalars().all())
        if ids is not None and len(found) != len(set(ids)):
            missing = set(ids) - {d.id for d in found}
            raise NotFoundError(
                f"Not in project '{project.name}' ({kind}): "
                + ", ".join(sorted(str(i) for i in missing))
            )
        return found

    async def _service(self, name: str) -> Service:
        service = await self.services.get_by_name(name)
        if service is None:
            raise ConflictError(
                f"Service '{name}' is not registered: is its worker running?"
            )
        return service

    async def _files(self, user: CurrentUser, file_ids: list[UUID]) -> list[StoredFile]:
        found = []
        for file_id in file_ids:
            obj = await self.session.get(StoredFile, file_id)
            # Same answer for "missing" and "not yours".
            if obj is None or not (user.is_admin or obj.owner_id == user.id):
                raise NotFoundError(f"File {file_id} not found.")
            found.append(obj)
        return found

    async def start(
        self, project_id: UUID, user: CurrentUser, data: RunCreate
    ) -> RunRead:
        project = await self.projects.get(project_id, user)

        # Resolve everything before creating anything: a run starts whole or not.
        selected: dict[str, list[Any]] = {}
        for kind, (_, _, field) in ANALYSES.items():
            definitions = await self._definitions(project, kind, getattr(data, field))
            if definitions:
                selected[kind] = definitions
        if not selected:
            raise ConflictError(
                "Nothing to apply: this project has no enabled definition "
                "(or none was selected)."
            )
        if data.anonymize and "entities" not in selected:
            raise ConflictError(
                "Anonymizing needs entities to hide: apply at least one entity."
            )
        files = await self._files(user, data.file_ids)
        parser = await self._service(PARSER) if files else None
        workers = {kind: await self._service(ANALYSES[kind][1]) for kind in selected}
        anonymizer = await self._service(ANONYMIZE) if data.anonymize else None

        parent = Task(
            user_id=user.id,
            project_id=project.id,
            status=TaskStatus.PENDING,
            input_data={
                "kind": "project_run",
                "source": "files" if files else "text",
                "file_ids": [str(f.id) for f in files],
                "selected": {k: [str(d.id) for d in v] for k, v in selected.items()},
                "anonymize": data.anonymize,
            },
        )
        self.session.add(parent)
        await self.session.flush()

        # step task -> the input its worker gets, when it differs from the row.
        clear_inputs: dict[uuid.UUID, dict[str, Any]] = {}
        steps: list[tuple[str, Task, Service]] = []
        parser_task: Task | None = None
        if files:
            parser_input: dict[str, Any] = {
                "files": [
                    {"s3_key": f.storage_key, "filename": f.filename, "mime": f.mime}
                    for f in files
                ]
            }
            if data.blur_screenshots is not None:
                parser_input["blur_screenshots"] = data.blur_screenshots
            parser_task = self._child(parent, user, parser.id, parser_input)
            steps.append(("parser", parser_task, parser))

        pages = None if files else text_to_pages(data.text or "")
        for kind, definitions in selected.items():
            step, _, _ = ANALYSES[kind]
            payload = build_inputs(kind, definitions)
            if parser_task is not None:
                payload["awaiting"] = str(parser_task.id)  # pages come later
            else:
                payload["pages"] = pages
            task = self._child(parent, user, workers[kind].id, payload)
            if data.anonymize and "pages" in payload:
                # The text is only sent, never stored: the row gets a masked copy.
                clear_inputs[task.id] = payload
                task.input_data = mask_text_fields(payload)
            steps.append((step, task, workers[kind]))
            if kind == "entities":
                ner_task = task

        if anonymizer is not None:
            # Waits for the ner task: it needs the entities, and the pages that
            # task received.
            anonymize_task = self._child(
                parent,
                user,
                anonymizer.id,
                {"awaiting": str(ner_task.id), "feed": "anonymize"},
            )
            steps.append(("anonymize", anonymize_task, anonymizer))

        for f in files:
            f.project_id = f.project_id or project.id  # files join the project
        await self.session.commit()

        # Text: every worker starts now. Files: only the parser does; the rest
        # is released when it succeeds.
        for _, task, _ in steps:
            if "awaiting" not in task.input_data:
                await self.tasks.dispatch(task, clear_inputs.get(task.id))

        return RunRead(
            id=parent.id,
            project_id=project.id,
            status=parent.status,
            steps=[
                RunStep(
                    task_id=task.id,
                    step=step,
                    service=service.name,
                    status=task.status,
                    waiting="awaiting" in task.input_data,
                )
                for step, task, service in steps
            ],
        )

    def _child(
        self, parent: Task, user: CurrentUser, service_id: UUID, input_data: dict
    ) -> Task:
        task = Task(
            # Known now: the analysis tasks name the parser task they wait for.
            id=uuid.uuid4(),
            parent_task_id=parent.id,
            project_id=parent.project_id,
            service_id=service_id,
            user_id=user.id,
            status=TaskStatus.PENDING,
            input_data=input_data,
        )
        self.session.add(task)
        return task
