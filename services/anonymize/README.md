# LiSA Service — Anonymize (llm-guard)

First LiSA worker service. It wraps [llm-guard's Anonymize input scanner](https://protectai.github.io/llm-guard/input_scanners/anonymize/)
to redact PII from prompts, and runs as a **Celery** worker backed by **Redis**.

On startup the worker **self-registers** against the LiSA backend
(`POST /api/v1/services`). If a service with the same name already exists, it is
reused and simply reported as *up*.

## Layout

```
services/anonymize/
├── Dockerfile            # build context = repo root (needs ../../worker)
├── pyproject.toml
└── app/
    ├── config.py         # env: REDIS_URL, LISA_API_URL, ...
    ├── service.py        # AnonymizeService(BaseService) + process()
    ├── celery_app.py     # Celery app + worker_ready self-registration
    └── tasks.py          # anonymize.scan task
```

## Run with Docker Compose

```bash
docker compose up redis server anonymize
```

## Local development

```bash
cd services/anonymize
uv pip install -e .            # resolves ../../worker via tool.uv.sources
python -m spacy download en_core_web_sm
celery -A app.celery_app.celery_app worker --loglevel=info
```

## Calling the task

```python
from app.tasks import scan

result = scan.delay({"prompt": "My name is John Doe, email john.doe@acme.com"}).get()
# {"sanitized": "My name is [REDACTED_PERSON_1], email [REDACTED_EMAIL_ADDRESS_1]",
#  "is_valid": False, "risk_score": 1.0, "flagged": True}
```

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker & result backend |
| `LISA_API_URL` | `http://localhost:8000` | Backend base URL for registration |
| `ANONYMIZE_THRESHOLD` | `0` | Scanner acceptance threshold |
| `ANONYMIZE_LANGUAGE` | `en` | Detection language |
