# LiSA Server

Async FastAPI backend for managing **services** and **tasks**, backed by
PostgreSQL (SQLAlchemy 2.0 async + asyncpg).

## Architecture

Layers are kept separate:

```
app/
  models/        # SQLAlchemy ORM models (Service, Task) + enums/mixins
  schemas/       # Pydantic request/response models
  repositories/  # Data-access layer (async CRUD)
  services/      # Business logic + domain exceptions
  api/           # FastAPI routers + dependencies
  config.py      # Settings (pydantic-settings)
  database.py    # Async engine/session + Base
  main.py        # App factory, lifespan, exception handlers
```

## Endpoints

- `GET /health` — liveness + DB check.
- `GET/POST /api/v1/services`, `GET/PATCH/DELETE /api/v1/services/{id}` — CRUD.
- `POST /api/v1/tasks` — submit a task.
- `GET /api/v1/tasks`, `GET /api/v1/tasks/{id}` — list/get.
- `GET /api/v1/tasks/{id}/status` — poll progress.
- `GET /api/v1/tasks/{id}/children` — execution graph children.
- `PATCH /api/v1/tasks/{id}` — update (status, progress, output…).
- `POST /api/v1/tasks/{id}/revoke` — cancel.
- `POST /api/v1/tasks/{id}/retry` — re-queue a failed/revoked task.
- `DELETE /api/v1/tasks/{id}` — delete.

Interactive docs at `/docs`.

## Run

With Docker Compose (from repo root):

```bash
docker compose up --build server db
```

Locally:

```bash
uv venv && uv pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://lisa:lisa@localhost:5432/lisa
uvicorn app.main:app --reload
```

## Tests

```bash
uv pip install -e ".[dev]"
pytest
```

> Tables are auto-created on startup. For production, manage schema changes
> with a migration tool such as Alembic.
