# LiSA safety service

Celery worker that checks each page of a parsed document for **malicious
prompts** and **PII**, in one pass, with the GLiNER2
[guardrails + PII checkpoint](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/16-safety_pii.md)
(`fastino/GLiNER2-Guardrails-PII-Multi`: English, French, Spanish, German,
Italian, Portuguese, Dutch).

- Service name: `safety` (type `guard`), queue `safety`.
- Input: the parser output, plus optional overrides.

  ```json
  {
    "pages": [{"page_number": 1, "content": "...", "words": [...]}],
    "pii_labels": ["email", {"name": "plate", "description": "A car plate"}],
    "safety_tasks": [{"name": "tone", "labels": ["polite", "rude"],
                      "ok_labels": ["polite"]}]
  }
  ```

  Only `content` and `page_number` are required; `words` (the parser's word
  boxes, with their `start`/`end` offsets) are optional and give the entities
  boxes. Omit `pii_labels` / `safety_tasks` for the defaults (see
  `app/defaults.py`: 15 common PII types, and the `prompt_safety`,
  `jailbreak_detection` and `prompt_toxicity` tasks); pass `[]` to skip one
  of the two. A label is a name or `{"name", "description"}`; a task's
  `ok_labels` are the ones meaning "nothing wrong" (any other makes the page
  unsafe).
- Output:

  ```json
  {"id": "...", "model": "gliner2:fastino/GLiNER2-Guardrails-PII-Multi",
   "unsafe": true, "has_pii": true,
   "pages": [{"page_number": 1, "unsafe": true, "has_pii": true,
     "safety": [{"name": "jailbreak_detection", "multi_label": true, "flagged": true,
                 "labels": [{"label": "jailbreak_attempt", "score": 0.56, "flagged": true}]}],
     "entities": [{"label": "email", "text": "john@acme.com", "start": 38, "end": 51,
                   "score": 1.0, "model": "gliner2:...",
                   "bboxes": [{"x": 0.2, "y": 0.1, "width": 0.2, "height": 0.02}]}]}]}
  ```

  `start`/`end` are character offsets into the page `content` (the same
  offsets as the parser's words, so a span can be redacted by the anonymize
  service). `bboxes` holds one relative (0-1) box per line the entity spans,
  empty without `words`.
- **Long pages** are read in full: the model scans them in overlapping windows
  (`CHUNK_SIZE` words, `CHUNK_OVERLAP` shared words), see
  [GLiNER2 long context](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/12-long_context.md).

## Changing the model

Everything model-specific lives in `app/guards.py`: another GLiNER2 checkpoint
only needs `SAFETY_MODEL` (also a build arg, baked into the image); another
model family is a class with `name` and `analyse(text, pii_labels, tasks)`,
registered in `BACKENDS` and selected with `SAFETY_BACKEND`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SAFETY_BACKEND` | `gliner2` | Guard implementation (key of `BACKENDS`) |
| `SAFETY_MODEL` | `fastino/GLiNER2-Guardrails-PII-Multi` | Model loaded by the backend |
| `PII_THRESHOLD` | `0.5` | Minimum score of a PII entity |
| `SAFETY_THRESHOLD` | `0.4` | Default minimum score of a multi-label safety class |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `384` / `64` | Long-context window and overlap, in words |
| `CELERY_QUEUE` | `safety` | Queue consumed |

## Tests

```bash
uv sync --extra dev   # from this directory
uv run pytest
```

The tests use a fake guard; the model is never loaded.
