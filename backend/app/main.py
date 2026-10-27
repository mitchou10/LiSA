import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router, health
from app.config import get_settings
from app.core.safe_logging import hide_exception_messages
from app.database import async_session_factory
from app.migrations import run_migrations
from app.services.detection_profile import DetectionProfileService
from app.services.exceptions import (
    ConflictError,
    GoneError,
    InvalidStateError,
    NotFoundError,
)
from app.services.purge import purge_loop

settings = get_settings()

# Tracebacks in the logs name the exception, not what it quotes of the documents.
hide_exception_messages("", "uvicorn", "uvicorn.error")


async def _seed_detection_profiles() -> None:
    """Create the default detection profiles (version 1) if missing."""
    async with async_session_factory() as session:
        await DetectionProfileService(session).ensure_defaults()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.run_migrations:
        await run_migrations()
    await _seed_detection_profiles()
    # Finished runs are purged once they are older than the retention.
    purger = (
        asyncio.create_task(purge_loop(async_session_factory))
        if settings.retention_days > 0
        else None
    )
    try:
        yield
    finally:
        if purger is not None:
            purger.cancel()
            with suppress(asyncio.CancelledError):
                await purger


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
    )


@app.exception_handler(ConflictError)
async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
    )


@app.exception_handler(GoneError)
async def gone_handler(_: Request, exc: GoneError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_410_GONE, content={"detail": str(exc)})


@app.exception_handler(InvalidStateError)
async def invalid_state_handler(_: Request, exc: InvalidStateError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
    )


# Health is mounted at the root, the rest under the versioned prefix.
app.include_router(health.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
