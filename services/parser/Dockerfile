# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Current packaging tools (the base image ships ones with known CVEs).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install the independent worker package first (path dependency).
COPY worker /worker
RUN uv pip install --system --no-cache /worker

COPY services/parser/pyproject.toml ./
COPY services/parser/README.md ./
COPY services/parser/app ./app
RUN uv pip install --system --no-cache --no-sources .

# Bake the Tesseract language data into the image (needs network at build time).
ARG OCR_LANGUAGE=eng+fra
ENV OCR_LANGUAGE=${OCR_LANGUAGE}
ENV HF_HOME=/opt/hf
RUN python -m app.warmup

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /opt/hf && chown -R app:app /app /opt/hf
USER app

HEALTHCHECK --interval=60s --timeout=20s --start-period=120s --retries=3 \
    CMD celery -A app.celery_app.celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
