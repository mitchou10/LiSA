# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_TORCH_BACKEND=cpu

# llm-guard / presidio / spacy need a compiler for some wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the independent worker package first (path dependency).
COPY worker /worker
RUN uv pip install --system --no-cache /worker

# Install the service (llm-guard pulls in torch; force CPU-only builds).
COPY services/anonymize/pyproject.toml ./
COPY services/anonymize/README.md ./
COPY services/anonymize/app ./app
RUN uv pip install --system --no-cache --no-sources --torch-backend=cpu .

# Pre-download the default spaCy model used by Presidio.
RUN python -m spacy download en_core_web_sm

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
