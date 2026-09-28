# LiSA GLiNER Service

Zero-shot multilingual Named Entity Recognition using [GLiNER](https://github.com/urchade/GLiNER).
Detects custom entity types — PII, police, health, legal, secrets — from a
configurable list of labels, in 100+ languages.

## Entity categories

| Category | Labels |
|----------|--------|
| **PII** | person, email address, phone number, physical address, date of birth, national ID |
| **POLICE** | police report, police officer, suspect, victim, witness, criminal record, investigation information, evidence |
| **HEALTH** | medical information, medical record, medical diagnosis, medical history, medication, prescription |
| **LEGAL** | legal information, court case, court decision, lawsuit, legal proceeding, lawyer, judge, prosecutor |
| **SECRET** | password, API key, access token, private key |

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `GLINER_MODEL` | `gliner-community/gliner_small-v2.5` | HuggingFace model to use |
| `GLINER_THRESHOLD` | `0.5` | Detection threshold (0-1) |
| `GLINER_LABELS` | *(all labels above)* | Comma-separated list of entity labels to detect |
| `CELERY_QUEUE` | `gliner-ner` | Celery queue to consume from |

## Running

```bash
docker compose up -d --build gliner
```
