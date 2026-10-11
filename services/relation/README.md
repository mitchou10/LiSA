# LiSA relation extraction service

Celery worker for **zero-shot relation extraction** with
[GLiNER2](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/6-relation_extraction.md)
(`fastino/gliner2.5-multi-v1` by default, multilingual): who or what is linked
to whom ("Tim Cook" `works_for` "Apple Inc."), page by page, with the span of
both ends.

- Service name: `relation` (type `analyser`), queue `relation`.
- Input: the parser output, plus optional relation types.

  ```json
  {
    "pages": [{"page_number": 1, "content": "...", "words": [...]}],
    "relations": ["married_to",
                  {"name": "prescribed", "threshold": 0.7,
                   "description": "The head is a doctor, the tail the patient"}],
    "threshold": 0.5
  }
  ```

  Only `content` and `page_number` are required; `words` (the parser's word
  boxes with their `start`/`end` offsets) give both ends boxes. Omit
  `relations` for the defaults (`app/defaults.py`: `works_for`, `lives_in`,
  `located_in`, `married_to`, `parent_of`); a bare string is a relation without
  description. **A relation is directional** (head -> tail): say which way in
  the description, and use a specific name (`works_for`, not `related`). The
  description noticeably improves accuracy.
- Output:

  ```json
  {"id": "...", "model": "gliner2:fastino/gliner2.5-multi-v1",
   "pages": [{"page_number": 1, "relations": [
     {"id": "r0", "relation": "works_for", "score": 0.995, "model": "gliner2:...",
      "head": {"text": "Tim Cook", "start": 0, "end": 8, "score": 0.995,
               "bboxes": [{"x": 0.1, "y": 0.1, "width": 0.15, "height": 0.02}]},
      "tail": {"text": "Apple Inc.", "start": 19, "end": 29, "score": 0.997,
               "bboxes": []}}]}]}
  ```

  `start`/`end` are character offsets into the page `content` (the same offsets
  as the parser's words, and as the `ner` service's entities). `bboxes` holds
  one relative (0-1) box per line the end spans, empty without `words`. The
  relation `score` is the lower of its two ends.
- **Long pages** are read in full, never truncated: the extractor uses
  [`extract_long`](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/12-long_context.md),
  which scans the page in overlapping windows (`CHUNK_SIZE` words,
  `CHUNK_OVERLAP` shared words) and returns global character offsets.
  **Both ends of a relation must fall in the same window**: a relation whose
  ends are further apart than the window is missed. The default overlap is
  therefore wider than for NER (128 words); raise it, or the window, if
  distant relations matter.

## Limits

Relations are decoded independently: the model does not check that the ends
have the right type (a `lives_in` may point to a company), nor that a relation
is unique or consistent with the others. Expect some wrong pairs on documents
with many entities; raise the threshold of the relations that matter and be
precise in their descriptions.

## Changing the model

Everything model-specific lives in `app/extractors.py`: another GLiNER2 /
GLiNER2.5 checkpoint only needs `RELATION_MODEL` (also a build arg, baked into
the image); another model family is a class with `name` and
`extract(text, rules, threshold)`, registered in `BACKENDS` and selected with
`RELATION_BACKEND`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RELATION_BACKEND` | `gliner2` | Extractor implementation (key of `BACKENDS`) |
| `RELATION_MODEL` | `fastino/gliner2.5-multi-v1` | Model loaded by the backend |
| `RELATION_THRESHOLD` | `0.5` | Minimum score of a relation (a relation can override it) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `384` / `128` | Long-context window and overlap, in words |
| `CELERY_QUEUE` | `relation` | Queue consumed |

## Tests

```bash
uv sync --extra dev   # from this directory
uv run pytest
```

The tests use a fake extractor; the model is never loaded.
