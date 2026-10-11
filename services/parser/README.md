# LiSA parser service (OCR)

Celery worker that turns PDFs and images into pages the rest of the pipeline
can use. Built on [LiteParse](https://github.com/run-llama/liteparse): native
PDF text extraction, Tesseract OCR only where a page has no text layer.

- Service name: `liteparse-ocr` (type `other`), queue `liteparse-ocr`.
- It reads the file, extracts the text and boxes, and takes the screenshots.
  Detection and anonymization happen in other services.
- Defaults: screenshots are **blurred** (irreversibly, text is unreadable even
  to OCR; the readable pixels are never stored), the source file is **deleted
  as soon as it has been read**, and the text and boxes are kept **in clear**.
- Input: `{"files": [{"s3_key", "filename", "mime"}], "blur_screenshots": true}`.
  `s3_key` is the key of the file in the bucket (`S3_BUCKET`), e.g. the
  `s3_key` returned by `POST /api/v1/files`. `filename` / `mime` tell the
  format (a key has no extension). `blur_screenshots` overrides
  `BLUR_SCREENSHOTS` for one task.
- Output: `{"pages": [{page_number, filename, width, height, content, lines, words, blurred, s3_key}]}`
  - `content` is the page text (one line per text line).
  - `lines` / `words` carry a **relative** box (`x`, `y`, `width`, `height`
    are fractions of the page between 0 and 1, origin top-left, the same
    convention as the anonymize `bboxes`) and `start`/`end` offsets
    into `content`. An analyser entity (`start_char`/`end_char`) maps to the
    words overlapping that range. Every box also carries `model`, the engine
    that produced it: `liteparse` (the PDF's own text layer) or `tesseract` (OCR). The page's own `width` / `height` (page units, e.g.
    PDF points) are kept to recover absolute positions.
  - `s3_key` is `pages/<task>/<file>/<source page>.png`, the page screenshot
    in object storage (the task fails if `S3_BUCKET` is not configured).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OCR_LANGUAGE` | `eng+fra` | Tesseract languages (also a build arg, baked into the image) |
| `MAX_FILE_MB` | `10` | Per-file size limit |
| `MAX_PAGES` | `50` | Pages kept per file |
| `S3_BUCKET` | – (required) | Bucket for the page screenshots |
| `S3_ENDPOINT_URL` / `S3_REGION` | – | S3 endpoint (RustFS: `http://rustfs:9000`) and region |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | – | Object storage credentials |
| `BLUR_SCREENSHOTS` | `true` | Blur the screenshots by default |
| `BLUR_MIN_RADIUS` / `BLUR_RATIO` | `20` / `0.03` | Gaussian blur radius (px): max(min, smallest side x ratio) |
| `DELETE_SOURCE_AFTER_PARSE` | `true` | Delete the source file from storage right after reading it |
| `CELERY_QUEUE` | `liteparse-ocr` | Queue consumed |

## Tests

```bash
pip install -e ../../worker -e ".[dev]"
pytest
```
