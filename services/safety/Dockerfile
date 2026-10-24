# syntax=docker/dockerfile:1

# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_TORCH_BACKEND=cpu

# torch needs a compiler for some wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Current packaging tools (the base image ships ones with known CVEs).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

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
ENV HF_HOME=/opt/hf
RUN python -m app.warmup

FROM python:3.12-slim AS runtime
# pip is a build tool: the runtime image never installs anything, and the pip bundled with the base
# image carries known CVEs. Removed rather than upgraded, so there is nothing left to keep patched.
RUN python -m pip uninstall -y pip
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /opt/hf && chown -R app:app /app /opt/hf
COPY --from=builder --chown=app:app /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder --chown=app:app /usr/local/bin /usr/local/bin
COPY --from=builder --chown=app:app /app/app /app/app
COPY --from=builder --chown=app:app /opt/hf /opt/hf
USER app

HEALTHCHECK --interval=60s --timeout=20s --start-period=120s --retries=3 \
    CMD celery -A app.celery_app.celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
