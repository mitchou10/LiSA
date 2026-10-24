from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: SessionDep) -> HealthRead:
    """Liveness/readiness probe including a database round-trip."""
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"
    return HealthRead(status="ok", database=db_status)
