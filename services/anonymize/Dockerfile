# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the independent worker package first (path dependency).
COPY worker /worker
RUN uv pip install --system --no-cache /worker

# Install the service.
COPY services/anonymize/pyproject.toml ./
COPY services/anonymize/README.md ./
COPY services/anonymize/app ./app
RUN uv pip install --system --no-cache --no-sources .

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
