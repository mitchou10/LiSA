# LiSA image classification service

Celery worker for **zero-shot image classification** with
[CLIP](https://huggingface.co/openai/clip-vit-base-patch32): you describe each
label in words, and every image gets the description it matches best. No
training, any label.

- Service name: `image-classification` (type `analyser`), queue
  `image-classification`.
- Input: images from the bucket, plus what to classify them as.

  ```json
  {
    "images": [{"s3_key": "uploads/3f2a..."}],
    "pages": [{"page_number": 1, "s3_key": "pages/<task>/1/1.png"}],
    "classifications": [
      {"name": "document_type", "labels": [
        {"name": "invoice", "description": "a scanned invoice with a table of amounts"},
        {"name": "id_card", "description": "an identity card with a photo and a name"},
        {"name": "photo", "description": "a photograph of a person or a place"}]},
      {"name": "content", "multi_label": true, "threshold": 0.3,
       "labels": ["a handwritten note", "a printed table", "a signature"]}
    ]
  }
  ```

  `images` are keys of images in the bucket (`S3_BUCKET`); `pages` is the
  parser's output, and every page with an `s3_key` (its screenshot) is
  classified too, pages without one are skipped. A label is
  `{"name", "description"}` or a bare string, and a classification needs at
  least two labels.
  **The description is what is matched with the image**: write it as what the
  image looks like ("a scanned invoice with a table of amounts"), in English
  (CLIP is English-only). A label without description is matched as
  `IMAGE_PROMPT_TEMPLATE` (`"a photo of {label}"`).
- Output:

  ```json
  {"id": "...", "model": "clip:openai/clip-vit-base-patch32",
   "images": [{"s3_key": "pages/t/1/1.png", "page_number": 1, "classifications": [
     {"name": "document_type", "multi_label": false, "labels": ["invoice"],
      "scores": {"invoice": 0.97},
      "probabilities": {"invoice": 0.97, "id_card": 0.02, "photo": 0.01}}]}]}
  ```

  Single-label returns the best label. Multi-label returns the labels whose
  probability reaches the `threshold` (default `IMAGE_THRESHOLD`), best first,
  possibly none. `scores` holds the returned labels' probabilities,
  `probabilities` those of **every** candidate.

## Limits

CLIP compares the image with all the descriptions at once: the probabilities
**sum to 1** over the candidates. So a multi-label threshold is a share of
that total, not an independent yes/no per label, and with many labels no
single one reaches a high value. Prefer a few distinct descriptions, and for an
"is it present?" question add a contrast label ("a page with no signature").

The parser blurs its screenshots by default: a blurred page keeps its layout (a
table, a photo, a form) but not its text, so classify what it *looks like*, not
what it says, or parse with `blur_screenshots: false`.

## Changing the model

Everything model-specific lives in `app/classifiers.py`. Another CLIP
checkpoint only needs `IMAGE_MODEL` (also a build arg, baked into the image),
e.g. `openai/clip-vit-large-patch14` (slower, more accurate). Another model
family is a class with `name` and `classify(image, task) -> {label: probability}`,
registered in `BACKENDS` and selected with `IMAGE_BACKEND`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `IMAGE_BACKEND` | `clip` | Classifier implementation (key of `BACKENDS`) |
| `IMAGE_MODEL` | `openai/clip-vit-base-patch32` | Model loaded by the backend |
| `IMAGE_PROMPT_TEMPLATE` | `a photo of {label}` | Matched for a label without description |
| `IMAGE_THRESHOLD` | `0.3` | Default multi-label threshold |
| `MAX_IMAGE_MB` | `20` | Largest image accepted |
| `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | – | Bucket the images are read from (the parser's) |
| `CELERY_QUEUE` | `image-classification` | Queue consumed |

## Tests

```bash
uv sync --extra dev   # from this directory
uv run pytest
```

The tests use a fake model and a fake bucket; CLIP is never loaded.
