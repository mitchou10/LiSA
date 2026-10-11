from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import AnalyticsServiceDep, CurrentUserDep
from app.schemas.analytics import DashboardStats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    service: AnalyticsServiceDep,
    user: CurrentUserDep,
    user_id: Annotated[
        str | None, Query(description="Scope stats to a single user (admins only).")
    ] = None,
    project_id: Annotated[
        UUID | None, Query(description="Scope stats to a single project.")
    ] = None,
    days: Annotated[
        int, Query(ge=1, le=365, description="Size of the analysis window in days.")
    ] = 30,
) -> DashboardStats:
    """Aggregated statistics for the monitoring dashboard."""
    # Someone who is not an admin only ever sees their own activity.
    if not user.is_admin:
        user_id = user.id
    return await service.dashboard(user_id=user_id, project_id=project_id, days=days)
