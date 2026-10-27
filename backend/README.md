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
- `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}` — projects (owner or admin only).
- `GET/POST /api/v1/projects/{id}/{entities|relations|classifications|safety}`, `GET/PATCH/DELETE .../{definition_id}` — what a project looks for (classification and safety carry labels; safety labels can be `is_ok`).
- `POST /api/v1/projects/{id}/runs` — analyse a `text` or `file_ids` with the project's definitions (omit a `*_ids` list for every enabled one, `[]` to skip a kind). A text goes straight to the analysis workers as pages; files go to the parser first and the analysis tasks wait for its pages. Returns the run: a parent task whose children are the workers, to poll with `/tasks`.
- `POST /api/v1/files` (multipart `file`) — store a file in object storage (RustFS, S3 API), returns its id, size and sha256.
- `GET /api/v1/files/{id}`, `GET /api/v1/files/{id}/content`, `DELETE /api/v1/files/{id}` — metadata / bytes / delete. Only the owner and admins (including the service token) can access a file.

Uploaded files live in the `S3_BUCKET` bucket (`S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `MAX_UPLOAD_MB`); the database only keeps their metadata. Only the backend talks to the object store: workers fetch their input through `GET /files/{id}/content` with the service token. A task refers to a file with `{"file_id": "...", "filename": "..."}`; the parser deletes the source once parsed (`DELETE_SOURCE_AFTER_PARSE`).

**Retention.** What a run's documents said (texts, entities, page images, file names, the replacement texts users set) is kept `RETENTION_DAYS` days after the run ends (default 7, `0` = until purged by hand), then purged, checked every `PURGE_INTERVAL_SECONDS`. A purge masks the texts with `*`, drops the image keys and deletes the images and the uploaded file from storage; task rows, labels, scores, offsets, boxes, durations and the boxes users drew stay, so the dashboard keeps its numbers. It can also be done on request (`POST /tasks/{run_id}/purge`) or with an export (`purge_after` in the render request). A purged run can no longer be rendered.

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

## Database migrations (Alembic)

The schema is managed by Alembic (`backend/migrations`). Migrations are applied
automatically at startup (`RUN_MIGRATIONS=true`, the default). Manually:

```bash
cd backend
alembic upgrade head                                  # apply
alembic revision --autogenerate -m "describe change"  # after editing models
```

Databases created before Alembic are adopted transparently: revision `0001`
only creates tables that are missing.

## Detection profiles

Editable, versioned service settings (currently the GLiNER labels, categories,
severities, actions and thresholds) live in `detection_profiles` /
`detection_profile_versions` (append-only). Routes under
`/api/v1/detection-profiles/{service_key}`: read for any user, write for admins.
Saving (or restoring) a version publishes `{"service_key", "version"}` on the
Redis channel `PROFILE_CHANNEL` (default `lisa:detection-profiles`) so workers
reload immediately; they also refresh every `PROFILE_REFRESH_SECONDS` (300) and
fall back to their environment defaults if the backend is unreachable.
