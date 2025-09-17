FROM python:3.13-slim AS builder
WORKDIR /app
# Install necessary packages
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest uv /usr/local/bin/uv
COPY apps/server/pyproject.toml apps/server/uv.lock  apps/server/.python-version /app/
RUN uv sync 
COPY apps/server/worker/ /app/worker/

ENV PYTHONPATH=/app

FROM builder AS guard
RUN uv sync --group guard
CMD ["uv", "run", "-m", "worker.main"]

FROM builder AS analyser
RUN uv sync --group analyser
CMD ["uv", "run", "-m", "worker.main"]

FROM builder AS test 
RUN uv sync --all-groups
COPY apps/server/tests/ /app/tests/

CMD [ "uv", "run", "pytest", "-v", "-s",  "--cov=/app/worker", "--cov-report=term-missing" ]