# LiSA parser service (OCR)

Celery worker that turns PDFs and images into pages the rest of the pipeline
can use. Built on [LiteParse](https://github.com/run-llama/liteparse): native
PDF text extraction, OCR only where a page has no text layer: Tesseract
(default) or PaddleOCR (`OCR_ENGINE=paddleocr`), which also detects the
orientation of each page.

- Service name: `liteparse-ocr` (type `other`), queue `liteparse-ocr`.
- It reads the file, extracts the text and boxes, and takes the screenshots.
  Detection and anonymization happen in other services.
- Defaults: screenshots are **blurred** (the text is unreadable, OCR included,
  while lines, blocks and tables stay visible; the readable pixels are never
  stored), the source file is **deleted
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
    that produced it: `liteparse` (the PDF's own text layer) or `tesseract` or `paddleocr` (OCR). The page's own `width` / `height` (page units, e.g.
    PDF points) are kept to recover absolute positions.
  - `orientation` is the clockwise rotation (0, 90, 180, 270) detected on a scanned
    page (always 0 unless `OCR_ENGINE=paddleocr`). The page is **not** turned: the
    screenshot, text and boxes stay as in the source. Every box carries `angle`,
    the clockwise rotation of its text; the box itself stays an axis-aligned
    fraction of the page, so the `ner`, `relation` and `safety` entity boxes
    carry the `angle` too, and the replacement text written in a box follows it.
  - `s3_key` is `pages/<task>/<file>/<source page>.png`, the page screenshot
    in object storage (the task fails if `S3_BUCKET` is not configured).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OCR_LANGUAGE` | `eng+fra` | Tesseract languages (also a build arg, baked into the image) |
| `OCR_ENGINE` | `tesseract` | `tesseract` or `paddleocr` (PP-OCRv5 via ONNX Runtime; build the image with `--build-arg OCR_ENGINE=paddleocr`, which installs the `paddle` extra and bakes the models in) |
| `DETECT_ORIENTATION` | `true` | PaddleOCR only: classify each scanned page (PP-LCNet doc orientation) and read it upright; boxes are mapped back onto the page as it is, with their `angle` |
| `ORIENTATION_MIN_SCORE` | `0.6` | Below this classifier score the page is left as it is |
| `PADDLE_MODELS_DIR` | `/models` | Folder of the ONNX models (`PADDLE_DET_MODEL`, `PADDLE_REC_MODEL`, `PADDLE_ORIENTATION_MODEL` name the sub-folders); `PADDLE_THREADS` (2) sets ONNX Runtime's threads |
| `MAX_FILE_MB` | `10` | Per-file size limit |
| `MAX_PAGES` | `50` | Pages kept per file |
| `S3_BUCKET` | – (required) | Bucket for the page screenshots |
| `S3_ENDPOINT_URL` / `S3_REGION` | – | S3 endpoint (RustFS: `http://rustfs:9000`) and region |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | – | Object storage credentials |
| `BLUR_SCREENSHOTS` | `true` | Blur the screenshots by default |
| `BLUR_MIN_RADIUS` / `BLUR_RATIO` | `4` / `0.007` | Gaussian blur radius (px): max(min, smallest side x ratio), ~8 px on a 1240 px page. Layout stays visible, text becomes unreadable (OCR included); under ~4 px it can be legible again |
| `DELETE_SOURCE_AFTER_PARSE` | `true` | Delete the source file from storage right after reading it |
| `CELERY_QUEUE` | `liteparse-ocr` | Queue consumed |

## Tests

```bash
pip install -e ../../worker -e ".[dev]"
pytest
```
