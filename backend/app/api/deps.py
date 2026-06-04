from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.service import ServiceService
from app.services.task import TaskService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service_service(session: SessionDep) -> ServiceService:
    return ServiceService(session)


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(session)


ServiceServiceDep = Annotated[ServiceService, Depends(get_service_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
