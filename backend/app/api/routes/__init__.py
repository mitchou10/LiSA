from fastapi import APIRouter

from app.api.routes import health, services, tasks

api_router = APIRouter()
api_router.include_router(services.router)
api_router.include_router(tasks.router)

__all__ = ["api_router", "health"]
