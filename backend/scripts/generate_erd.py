"""Render the data model (SQLAlchemy models) as an ER diagram with eralchemy2.

    uv run --with eralchemy2 python scripts/generate_erd.py ../docs/data-model.png

Reads the models, not a database, so it needs neither PostgreSQL nor Alembic.
The output format follows the extension (.png, .svg, .pdf, .dot, .er).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The app builds its engine at import time; this one is never connected to.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://erd:erd@localhost/erd")

from eralchemy2 import render_er
from sqlalchemy import JSON, DateTime, Uuid
from sqlalchemy.ext.compiler import compiles

from app import models  # noqa: F401 - registers every model on the metadata
from app.database import Base


# The diagram is drawn from the models, without a database: show the types
# PostgreSQL really uses instead of SQLAlchemy's generic fallbacks.
@compiles(Uuid)
def _uuid(type_, compiler, **kw) -> str:
    return "UUID"


@compiles(JSON)
def _json(type_, compiler, **kw) -> str:
    return "JSONB"


@compiles(DateTime)
def _datetime(type_, compiler, **kw) -> str:
    return "TIMESTAMPTZ" if type_.timezone else "TIMESTAMP"


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "data-model.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    render_er(Base.metadata, str(output), title="LiSA data model")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
