# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_TORCH_BACKEND=cpu

# torch needs a compiler for some wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the independent worker package first (path dependency).
COPY worker /worker
RUN uv pip install --system --no-cache /worker

# Install the service (gliner2 pulls in torch; force CPU-only builds).
COPY services/safety/pyproject.toml ./
COPY services/safety/README.md ./
COPY services/safety/app ./app
RUN uv pip install --system --no-cache --no-sources --torch-backend=cpu .

# Bake the model into the image (needs network at build time).
ARG SAFETY_MODEL=fastino/GLiNER2-Guardrails-PII-Multi
ENV SAFETY_MODEL=${SAFETY_MODEL}
RUN python -m app.warmup

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
