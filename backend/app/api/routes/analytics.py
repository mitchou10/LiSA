from fastapi import APIRouter, Query

from app.api.deps import AnalyticsServiceDep, CurrentUserDep
from app.schemas.analytics import DashboardStats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    service: AnalyticsServiceDep,
    _user: CurrentUserDep,
    user_id: str | None = Query(
        default=None, description="Scope stats to a single user."
    ),
    days: int = Query(
        default=30, ge=1, le=365, description="Size of the analysis window in days."
    ),
) -> DashboardStats:
    """Aggregated statistics for the monitoring dashboard."""
    return await service.dashboard(user_id=user_id, days=days)
