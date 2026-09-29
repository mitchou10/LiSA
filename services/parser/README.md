# LiSA parser service (OCR)

Celery worker that turns PDFs and images into pages the rest of the pipeline
can use. Built on [LiteParse](https://github.com/run-llama/liteparse): native
PDF text extraction, Tesseract OCR only where a page has no text layer.

- Service name: `liteparse-ocr` (type `other`), queue `liteparse-ocr`.
- Input: `{"files": [{"filename", "mime", "data_base64"}], "blur_screenshots": false}`.
  With `blur_screenshots: true` the page images are Gaussian-blurred in the worker (irreversibly, text is unreadable even to OCR); the unblurred pixels are never returned or stored.
- Output: `{"pages": [{page_number, filename, width, height, content, lines, words, image}]}`
  - `content` is the page text (one line per text line).
  - `lines` / `words` carry a box (`x`, `y`, `width`, `height` in the
    `width` x `height` page space, origin top-left) and `start`/`end` offsets
    into `content`. An analyser entity (`start_char`/`end_char`) maps to the
    words overlapping that range.
  - `image` is a PNG data URL of the rendered page.
- The uploaded bytes are removed from the stored task once parsed.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OCR_LANGUAGE` | `eng+fra` | Tesseract languages (also a build arg, baked into the image) |
| `MAX_FILE_MB` | `10` | Per-file size limit |
| `MAX_PAGES` | `50` | Pages kept per file |
| `BLUR_MIN_RADIUS` / `BLUR_RATIO` | `20` / `0.03` | Gaussian blur radius (px) when `blur_screenshots` is set: max(min, smallest side x ratio) |
| `CELERY_QUEUE` | `liteparse-ocr` | Queue consumed |

## Tests

```bash
pip install -e ../../worker -e ".[dev]"
pytest
```
