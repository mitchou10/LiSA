# LiSA NER service

Celery worker for **zero-shot named entity recognition** with
[GLiNER2](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/2-ner.md)
(`fastino/gliner2.5-multi-v1` by default, multilingual). It replaces the
former `gliner` service.

- Service name: `ner` (type `analyser`), queue `ner`.
- **What to look for** comes from the live detection profile edited in LiSA
  (labels, categories, severities, actions, thresholds; profile key
  `gliner-ner`). It follows profile changes without a restart, and falls back
  to the seeded defaults (`app/defaults.py`) if the backend cannot be reached.
  A run can also bring its own labels, on demand.
- Input: the parser output, plus optional overrides.

  ```json
  {
    "pages": [{"page_number": 1, "content": "...", "words": [...]}],
    "entities": ["iban", {"label": "plate", "description": "A car plate",
                          "category": "id", "severity": "high",
                          "action": "redact", "threshold": 0.7}],
    "threshold": 0.5
  }
  ```

  Only `content` and `page_number` are required; `words` (the parser's word
  boxes with their `start`/`end` offsets) give the entities boxes. `entities`
  replaces the profile for this run (a bare string is a label with the default
  rule); `threshold` overrides the global cutoff. A **description** tells the
  model what the label means and noticeably improves accuracy.
- Output:

  ```json
  {"id": "...", "model": "gliner2:fastino/gliner2.5-multi-v1",
   "profile_version": 3, "flagged": true, "severity": "high", "action": "redact",
   "pages": [{"page_number": 1, "flagged": true, "severity": "high", "action": "redact",
     "entities": [{"id": "e0", "label": "email address", "category": "PII",
                   "text": "john@acme.com", "start": 38, "end": 51, "score": 0.97,
                   "severity": "medium", "action": "redact", "flagged": true,
                   "model": "gliner2:...",
                   "bboxes": [{"x": 0.2, "y": 0.1, "width": 0.2, "height": 0.02}]}]}]}
  ```

  `start`/`end` are character offsets into the page `content` (the same offsets
  as the parser's words, so a span can be redacted by the anonymize service).
  `bboxes` holds one relative (0-1) box per line the entity spans, empty
  without `words`. `flagged` is false for an `allow` label; the page and
  document `severity` / `action` are the highest of their flagged entities.
- **Long pages** are read in full, never truncated: the extractor uses
  [`extract_long`](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/12-long_context.md),
  which scans the page in overlapping windows (`CHUNK_SIZE` words,
  `CHUNK_OVERLAP` shared words), de-duplicates the overlaps and returns global
  character offsets. An entity cut across two windows can be missed: raise the
  overlap if that happens.

## Changing the model

Everything model-specific lives in `app/extractors.py`: another GLiNER2 /
GLiNER2.5 checkpoint only needs `NER_MODEL` (also a build arg, baked into the
image); another model family is a class with `name` and
`extract(text, rules, threshold)`, registered in `BACKENDS` and selected with
`NER_BACKEND`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `NER_BACKEND` | `gliner2` | Extractor implementation (key of `BACKENDS`) |
| `NER_MODEL` | `fastino/gliner2.5-multi-v1` | Model loaded by the backend |
| `NER_THRESHOLD` | `0.5` | Default cutoff (the profile's threshold wins when it is used) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `384` / `64` | Long-context window and overlap, in words |
| `PROFILE_ENABLED` | `true` | Fetch the detection profile from the backend |
| `PROFILE_KEY` | `gliner-ner` | Profile key on the backend |
| `CELERY_QUEUE` | `ner` | Queue consumed |

## Tests

```bash
uv sync --extra dev   # from this directory
uv run pytest
```

The tests use a fake extractor; the model is never loaded.
