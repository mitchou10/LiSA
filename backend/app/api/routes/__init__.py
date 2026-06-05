from fastapi import APIRouter

from app.api.routes import analytics, auth, health, services, tasks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(services.router)
api_router.include_router(tasks.router)
api_router.include_router(analytics.router)

__all__ = ["api_router", "health"]
