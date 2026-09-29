# Build context must be the repository root (see docker-compose.yml) so that
# both the worker package and this service can be copied.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

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
RUN python -m app.warmup

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
