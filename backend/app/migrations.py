"""Run Alembic migrations programmatically (used at application startup)."""

from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config


def _upgrade_sync() -> None:
    # alembic.ini and migrations/ live next to ``app`` in the backend root
    # (the process working directory, /app in the container).
    command.upgrade(Config("alembic.ini"), "head")


async def run_migrations() -> None:
    """Upgrade the schema to head without blocking the event loop.

    env.py starts its own event loop, so it must run in a worker thread.
    """
    await asyncio.to_thread(_upgrade_sync)
