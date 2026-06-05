from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.analytics import AnalyticsService
from app.services.service import ServiceService
from app.services.task import TaskService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service_service(session: SessionDep) -> ServiceService:
    return ServiceService(session)


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(session)


def get_analytics_service(session: SessionDep) -> AnalyticsService:
    return AnalyticsService(session)


ServiceServiceDep = Annotated[ServiceService, Depends(get_service_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
