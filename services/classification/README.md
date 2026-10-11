# LiSA classification service

Celery worker that labels **each page** of a parsed document against a list of
classifications, each one **single-label** (exactly one label per page) or
**multi-label** (every label that applies). The model is swappable: GLiNER2
(`gliner2.5-multi-v1`) by default.

- Service name: `classification` (type `analyser`), queue `classification`.
- Input: the parser output plus what to look for.

  ```json
  {
    "pages": [{"page_number": 1, "content": "Facture n° 42 ..."}],
    "classifications": [
      {"name": "doc_type", "labels": [
        {"name": "invoice", "description": "A bill asking for a payment"},
        {"name": "contract", "description": "A signed agreement between parties"},
        "other"]},
      {"name": "topics", "labels": ["health", "legal", "finance"],
       "multi_label": true, "threshold": 0.4}
    ]
  }
  ```

  A label is `{"name", "description"}` (the description tells the model what
  the label means, which helps with similar labels) or a bare string for a
  label without description.

  Pages may be the parser's full pages: only `content` and `page_number` are
  read. `threshold` (0-1) applies to multi-label tasks only.
- Output:

  ```json
  {"id": "...", "model": "gliner2:fastino/gliner2.5-multi-v1",
   "pages": [{"page_number": 1, "classifications": [
     {"name": "doc_type", "multi_label": false, "labels": ["invoice"]},
     {"name": "topics", "multi_label": true, "labels": ["finance"]}]}]}
  ```

  `labels` is always a list: one element in single-label mode, empty when
  nothing applies (or the page is blank). Only labels from the request are
  ever returned.
- **Long pages** are read in full, not truncated: the GLiNER2 backend uses
  [`classify_text_long`](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/12-long_context.md),
  which scans the page in overlapping windows (`CLASSIFIER_CHUNK_SIZE` words,
  `CLASSIFIER_CHUNK_OVERLAP` shared words) and merges the per-window scores:
  the most confident prediction wins. A custom backend is responsible for
  handling long pages itself.

## Changing the model

Everything model-specific lives in `app/classifiers.py`.

- Another GLiNER2 / GLiNER2.5 checkpoint (span or boundary): set `CLASSIFIER_MODEL`
  (also a build arg, baked into the image).
- Another model family: add a class with a `name` property and
  `classify(text, task) -> list[str]`, register it in `BACKENDS`, set
  `CLASSIFIER_BACKEND`. Nothing else changes.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `CLASSIFIER_BACKEND` | `gliner2` | Classifier implementation (key of `BACKENDS`) |
| `CLASSIFIER_MODEL` | `fastino/gliner2.5-multi-v1` | Model loaded by the backend |
| `CLASSIFIER_THRESHOLD` | `0.4` | Default multi-label threshold |
| `CLASSIFIER_CHUNK_SIZE` | `384` | Window size, in whitespace words, for long pages |
| `CLASSIFIER_CHUNK_OVERLAP` | `64` | Words shared by adjacent windows (raise it if labels often sit on a boundary) |
| `CELERY_QUEUE` | `classification` | Queue consumed |

## Tests

```bash
uv sync --extra dev   # from this directory
uv run pytest
```

The tests use a fake classifier; the model is never loaded.
