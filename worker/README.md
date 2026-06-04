# LiSA Worker

Independent worker package containing HTTP clients that call the LiSA backend
routes. It has **no dependency on the backend code** — it only speaks HTTP, so
it can run as a standalone process or service.

## Layout

```
worker/
└── worker/
    └── core/
        └── client/
            ├── base.py       # BaseClient (httpx wrapper, error handling)
            ├── health.py     # HealthClient   -> /health
            ├── services.py   # ServiceClient  -> /api/v1/services
            ├── tasks.py      # TaskClient     -> /api/v1/tasks
            └── __init__.py   # LisaClient (aggregate facade)
```

## Install

```bash
cd worker
pip install -e .
```

## Configuration

The base URL is resolved in this order:

1. explicit argument: `LisaClient("http://my-host:8000")`
2. environment variable `LISA_API_URL`
3. default `http://localhost:8000`

## Usage

```python
from worker.core.client import LisaClient

with LisaClient() as lisa:
    print(lisa.health.check())                 # GET /health

    services = lisa.services.list()            # GET /api/v1/services

    task = lisa.tasks.submit({                  # POST /api/v1/tasks
        "user_id": "worker",
        "input_data": {"pages": [{"content": "hello"}]},
    })
    status = lisa.tasks.status(task["id"])      # GET /tasks/{id}/status
    lisa.tasks.retry(task["id"])                # POST /tasks/{id}/retry
    lisa.tasks.revoke(task["id"])               # POST /tasks/{id}/revoke
```

Each client can also be used on its own:

```python
from worker.core.client import TaskClient

with TaskClient("http://localhost:8000") as tasks:
    tasks.list(user_id="worker")
```

Errors from the backend raise `worker.core.client.ClientError` with
`status_code` and `detail` attributes.
