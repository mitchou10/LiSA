"""Tests for ParserService (runs the real LiteParse on generated documents)."""

from __future__ import annotations

import io

import pytest
from app.config import settings
from app.errors import ParserError
from app.imaging import blur_png
from app.layout import _unit, build_page
from app.service import ParserService, _suffix
from app.storage import Storage
from botocore.exceptions import ClientError


class FakeS3:
    """In-memory stand-in for the boto3 client (sources and screenshots)."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict] = []

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.puts.append(
            {"Bucket": Bucket, "Key": Key, "Body": Body, "ContentType": ContentType}
        )
        self.objects[Key] = Body

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET", "lisa-files")
    return ParserService(storage=Storage(client=FakeS3()))


@pytest.fixture
def quiet(service, mocker):
    """No backend: task updates are swallowed."""
    return mocker.patch.object(service, "update_task")


def _assert_offsets_match(page):
    """Every word's start/end must slice its text out of the page content."""
    assert page["words"], "expected word boxes"
    for w in page["words"]:
        assert page["content"][w["start"] : w["end"]] == w["text"]
    for line in page["lines"]:
        assert page["content"][line["start"] : line["end"]] == line["text"]


class TestHelpers:
    def test_suffix_from_name_then_mime(self):
        assert _suffix("Scan.PNG", None) == ".png"
        assert _suffix("noext", "application/pdf") == ".pdf"
        assert _suffix("noext", None) == ""


class TestPdf:
    def test_native_text_and_word_boxes(self, service, pdf_bytes):
        pages = service.parse_file(
            "doc.pdf", "application/pdf", pdf_bytes, key_prefix="p"
        )
        assert len(pages) == 2
        first = pages[0]
        assert "john@example.com" in first["content"]
        assert first["width"] > 0 and first["height"] > 0
        assert first["s3_key"] == "p/1.png"
        # Native PDF text: every box says which engine produced it.
        assert {b["model"] for b in (*first["words"], *first["lines"])} == {"liteparse"}
        assert "image_bytes" not in first and "image" not in first
        _assert_offsets_match(first)
        email = next(w for w in first["words"] if w["text"] == "john@example.com")
        # Relative boxes: fractions of the page, always within 0-1.
        for box in (email, *first["words"], *first["lines"]):
            for k in ("x", "y", "width", "height"):
                assert 0 <= box[k] <= 1
            assert box["x"] + box["width"] <= 1 + 1e-9
            assert box["y"] + box["height"] <= 1 + 1e-9

    def test_entity_offsets_map_to_boxes(self, service, pdf_bytes):
        """An analyser's start_char/end_char selects the matching word boxes."""
        page = service.parse_file("doc.pdf", None, pdf_bytes, key_prefix="p")[0]
        start = page["content"].index("john@example.com")
        end = start + len("john@example.com")
        hit = [w for w in page["words"] if w["start"] < end and w["end"] > start]
        assert [w["text"] for w in hit] == ["john@example.com"]


class TestImageOcr:
    def test_ocr_text_and_proportional_words(self, service, png_bytes):
        try:
            pages = service.parse_file(
                "scan.png", "image/png", png_bytes, key_prefix="p"
            )
        except ParserError as exc:  # tessdata download unavailable (offline CI)
            pytest.skip(str(exc))
        page = pages[0]
        assert "Marie Curie" in page["content"]
        # OCR text: the boxes come from Tesseract, with a confidence.
        assert {b["model"] for b in (*page["words"], *page["lines"])} == {"tesseract"}
        assert page["lines"][0]["confidence"] is not None
        _assert_offsets_match(page)
        words = page["words"]
        # Proportional split keeps words ordered left to right inside the line.
        assert [w["x"] for w in words] == sorted(w["x"] for w in words)
        line = page["lines"][0]
        assert all(line["x"] <= w["x"] <= line["x"] + line["width"] for w in words)


class TestProcess:
    def _files(self, service, *entries):
        """Put sources in the fake bucket and return the matching input."""
        files = []
        for key, name, data in entries:
            service.storage.client.objects[key] = data
            files.append({"s3_key": key, "filename": name})
        return {"files": files}

    def test_numbers_pages_across_files(self, service, pdf_bytes, quiet):
        result = service.process(
            self._files(
                service,
                ("uploads/a", "a.pdf", pdf_bytes),
                ("uploads/b", "b.pdf", pdf_bytes),
            )
        )
        assert [p["page_number"] for p in result["pages"]] == [1, 2, 3, 4]
        assert [p["filename"] for p in result["pages"]] == ["a.pdf"] * 2 + ["b.pdf"] * 2
        assert result["error"] is None

    def test_reports_progress_and_success(self, service, pdf_bytes, mocker):
        update = mocker.patch.object(service, "update_task")
        service.process(
            self._files(service, ("uploads/a", "a.pdf", pdf_bytes)), task_id="t1"
        )
        statuses = [c.kwargs.get("status") for c in update.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"

    def test_source_deleted_and_screenshots_stored(self, service, pdf_bytes, quiet):
        s3 = service.storage.client
        result = service.process(
            self._files(service, ("uploads/a", "a.pdf", pdf_bytes)), task_id="t3"
        )
        assert "uploads/a" not in s3.objects
        assert [p["s3_key"] for p in result["pages"]] == [
            "pages/t3/1/1.png",
            "pages/t3/1/2.png",
        ]
        assert set(s3.objects) == {"pages/t3/1/1.png", "pages/t3/1/2.png"}

    def test_source_kept_when_deletion_disabled(
        self, service, pdf_bytes, quiet, monkeypatch
    ):
        monkeypatch.setattr(settings, "DELETE_SOURCE_AFTER_PARSE", False)
        service.process(self._files(service, ("uploads/a", "a.pdf", pdf_bytes)))
        assert "uploads/a" in service.storage.client.objects

    def test_filename_defaults_to_key_name(self, service, pdf_bytes, quiet):
        service.storage.client.objects["docs/report.pdf"] = pdf_bytes
        result = service.process({"files": [{"s3_key": "docs/report.pdf"}]})
        assert result["pages"][0]["filename"] == "report.pdf"

    def test_missing_source_fails_the_task(self, service, mocker):
        update = mocker.patch.object(service, "update_task")
        with pytest.raises(ParserError, match="Cannot fetch"):
            service.process({"files": [{"s3_key": "nope", "filename": "a.pdf"}]})
        assert update.call_args.kwargs["status"] == "error"

    def test_file_without_key_is_rejected(self, service, quiet):
        with pytest.raises(ParserError, match="s3_key"):
            service.process({"files": [{"filename": "a.pdf"}]})

    @pytest.mark.parametrize("payload", [None, {}, {"files": []}])
    def test_requires_files(self, service, quiet, payload):
        with pytest.raises(ParserError, match="No file"):
            service.process(payload)

    def test_marks_task_failed_on_bad_file(self, service, mocker):
        update = mocker.patch.object(service, "update_task")
        service.storage.client.objects["uploads/x"] = b"plain text"
        with pytest.raises(ParserError):
            service.process(
                {"files": [{"s3_key": "uploads/x", "filename": "x.txt"}]}, task_id="t2"
            )
        assert update.call_args.kwargs["status"] == "error"

    def test_file_size_limit(self, service, monkeypatch):
        monkeypatch.setattr(settings, "MAX_FILE_MB", 0.0001)
        with pytest.raises(ParserError, match="limit"):
            service.parse_file("big.pdf", None, b"x" * 1000, key_prefix="p")


class _Item:
    def __init__(self, text, x=0, y=0, width=10, height=5, confidence=None):
        self.text, self.x, self.y, self.width, self.height = text, x, y, width, height
        self.confidence, self.words = confidence, []


class _Parsed:
    def __init__(self, items, width=100, height=100):
        self.text_items, self.width, self.height = items, width, height


def test_build_page_normalizes_boxes_to_the_page():
    page = build_page(
        _Parsed([_Item("hello", 50, 100, 100, 20)], width=200, height=400)
    ).model_dump()
    assert (page["width"], page["height"]) == (200, 400)  # page units kept
    line = page["lines"][0]
    assert (line["x"], line["y"], line["width"], line["height"]) == (
        0.25,
        0.25,
        0.5,
        0.05,
    )
    word = page["words"][0]
    assert (word["x"], word["width"]) == (0.25, 0.5)


def test_unit_clamps_and_handles_empty_page():
    assert _unit(50, 200) == 0.25
    assert _unit(-5, 200) == 0.0
    assert _unit(300, 200) == 1.0
    assert _unit(10, 0) == 0.0


def test_build_page_skips_blank_lines():
    page = build_page(
        _Parsed([_Item("hello world"), _Item("   "), _Item("bye")])
    ).model_dump()
    assert page["content"] == "hello world\nbye"
    assert [w["text"] for w in page["words"]] == ["hello", "world", "bye"]
    _assert_offsets_match(page)


def test_boxes_carry_the_model_that_produced_them():
    page = build_page(
        _Parsed([_Item("native text"), _Item("scanned text", confidence=0.93)])
    )
    native, ocr = page.lines
    assert native.model == "liteparse" and ocr.model == "tesseract"
    assert [w.model for w in page.words] == ["liteparse"] * 2 + ["tesseract"] * 2
    assert ocr.confidence == 0.93


class TestPageImageStorage:
    def test_fails_before_reading_without_bucket(self, service, quiet, monkeypatch):
        monkeypatch.setattr(settings, "S3_BUCKET", "")
        service.storage.client.objects["uploads/a"] = b"x"
        with pytest.raises(ParserError, match="S3_BUCKET"):
            service.process({"files": [{"s3_key": "uploads/a", "filename": "a.pdf"}]})
        assert (
            "uploads/a" in service.storage.client.objects
        )  # the source is not consumed

    def test_screenshots_uploaded_as_png_and_bytes_not_returned(
        self, service, pdf_bytes
    ):
        pages = service.parse_file(
            "a.pdf", "application/pdf", pdf_bytes, key_prefix="pages/t1/1"
        )
        puts = service.storage.client.puts
        assert len(puts) == len(pages) == 2
        assert puts[0]["Key"] == "pages/t1/1/1.png"
        assert puts[0]["Bucket"] == "lisa-files"
        assert puts[0]["ContentType"] == "image/png"
        assert puts[0]["Body"].startswith(b"\x89PNG")
        assert pages[0]["s3_key"] == "pages/t1/1/1.png"
        # Bytes go to S3 only: nothing image-like in the pages.
        assert all("image_bytes" not in p and "image" not in p for p in pages)


class TestBlur:
    def test_blurred_by_default_boxes_and_text_stay_clear(self, service, png_bytes):
        try:
            blurred = service.parse_file(
                "scan.png", "image/png", png_bytes, key_prefix="b"
            )[0]
        except ParserError as exc:  # tessdata download unavailable (offline CI)
            pytest.skip(str(exc))
        clear = service.parse_file(
            "scan.png", "image/png", png_bytes, key_prefix="c", blur=False
        )[0]
        assert blurred["blurred"] is True and clear["blurred"] is False
        objects = service.storage.client.objects
        assert objects["b/1.png"] != objects["c/1.png"]
        # Text and boxes are untouched by the blur.
        assert blurred["content"] == clear["content"]
        assert blurred["words"] == clear["words"]
        _assert_offsets_match(blurred)

    def test_blur_keeps_dimensions(self, png_bytes):
        from PIL import Image

        before = Image.open(io.BytesIO(png_bytes)).size
        after = Image.open(io.BytesIO(blur_png(png_bytes))).size
        assert before == after

    def _blur_used(self, service, pdf_bytes, mocker, extra=None):
        service.storage.client.objects["uploads/a"] = pdf_bytes
        mocker.patch.object(service, "update_task")
        spy = mocker.spy(service, "parse_file")
        service.process(
            {"files": [{"s3_key": "uploads/a", "filename": "a.pdf"}], **(extra or {})}
        )
        return spy.call_args.kwargs["blur"]

    def test_process_blurs_by_default(self, service, pdf_bytes, mocker):
        assert self._blur_used(service, pdf_bytes, mocker) is True

    def test_process_can_disable_blur(self, service, pdf_bytes, mocker):
        extra = {"blur_screenshots": False}
        assert self._blur_used(service, pdf_bytes, mocker, extra) is False

    def test_config_default_can_disable_blur(
        self, service, pdf_bytes, mocker, monkeypatch
    ):
        monkeypatch.setattr(settings, "BLUR_SCREENSHOTS", False)
        assert self._blur_used(service, pdf_bytes, mocker) is False

    def test_source_deleted_even_if_parsing_fails(self, service, mocker):
        service.storage.client.objects["uploads/x"] = b"not a pdf"
        mocker.patch.object(service, "update_task")
        mocker.patch.object(
            service, "parse_file", side_effect=ParserError("cannot parse")
        )
        with pytest.raises(ParserError):
            service.process({"files": [{"s3_key": "uploads/x", "filename": "x.pdf"}]})
        assert "uploads/x" not in service.storage.client.objects


def test_settings_celery_urls_default_to_redis(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    cfg = Settings(REDIS_URL="redis://r:6379/1")
    assert cfg.CELERY_BROKER_URL == cfg.CELERY_RESULT_BACKEND == "redis://r:6379/1"
    cfg = Settings(REDIS_URL="redis://r", CELERY_BROKER_URL="amqp://b")
    assert cfg.CELERY_BROKER_URL == "amqp://b"


def test_settings_read_the_environment(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("BLUR_SCREENSHOTS", "false")
    monkeypatch.setenv("MAX_FILE_MB", "2.5")
    cfg = Settings()
    assert cfg.BLUR_SCREENSHOTS is False and cfg.MAX_FILE_MB == 2.5


class _FakeOcr:
    """Stands in for PaddleOCR: one line, a box in pixels of the image it is given."""

    def __init__(self):
        self.seen: list[tuple[int, int]] = []

    def predict(self, image):
        self.seen.append((image.shape[1], image.shape[0]))
        return [
            {
                "rec_texts": ["Marie Curie", "  "],
                "rec_scores": [0.98, 0.5],
                "rec_boxes": [[90, 20, 450, 80], [0, 0, 1, 1]],
            }
        ]


class _FakeClassifier:
    def __init__(self, label="0", score=0.99):
        self.label, self.score = label, score

    def predict(self, image):
        return [{"label_names": [self.label], "scores": [self.score]}]


@pytest.fixture
def paddle_service(service, monkeypatch):
    from app.paddle import PaddleEngine

    monkeypatch.setattr(settings, "OCR_ENGINE", "paddleocr")
    ocr = _FakeOcr()
    classifier = _FakeClassifier()
    service.paddle = PaddleEngine(
        ocr_factory=lambda: ocr, orientation_factory=lambda: classifier
    )
    service.fake_ocr, service.fake_classifier = ocr, classifier
    return service


class TestPaddleOcr:
    def test_scanned_image_is_read_by_paddleocr(self, paddle_service, png_bytes):
        page = paddle_service.parse_file(
            "scan.png", "image/png", png_bytes, key_prefix="p"
        )[0]
        assert page["content"] == "Marie Curie"
        assert {b["model"] for b in (*page["words"], *page["lines"])} == {"paddleocr"}
        assert page["lines"][0]["confidence"] == 0.98
        assert page["orientation"] == 0
        _assert_offsets_match(page)
        for box in page["lines"]:
            assert 0 <= box["x"] and box["x"] + box["width"] <= 1 + 1e-9
            assert 0 <= box["y"] and box["y"] + box["height"] <= 1 + 1e-9

    def test_pdf_with_text_layer_is_not_ocrised(self, paddle_service, pdf_bytes):
        pages = paddle_service.parse_file("d.pdf", None, pdf_bytes, key_prefix="p")
        assert {b["model"] for b in pages[0]["words"]} == {"liteparse"}
        assert paddle_service.fake_ocr.seen == []

    def test_rotated_page_is_turned_upright(self, paddle_service, png_bytes):
        from PIL import Image

        paddle_service.fake_classifier.label = "90"
        # The same scan, rotated 90 degrees clockwise.
        with Image.open(io.BytesIO(png_bytes)) as image:
            buf = io.BytesIO()
            image.rotate(-90, expand=True).save(buf, format="PNG")
        page = paddle_service.parse_file(
            "scan.png", "image/png", buf.getvalue(), key_prefix="p", blur=False
        )[0]
        assert page["orientation"] == 90
        stored = Image.open(
            io.BytesIO(paddle_service.storage.client.objects["p/1.png"])
        )
        # Upright again: wider than tall, and OCR saw the upright image.
        assert stored.width > stored.height
        assert paddle_service.fake_ocr.seen == [stored.size]

    def test_unsure_classifier_leaves_the_page(self, paddle_service, png_bytes):
        paddle_service.fake_classifier.label = "180"
        paddle_service.fake_classifier.score = 0.2
        page = paddle_service.parse_file(
            "scan.png", "image/png", png_bytes, key_prefix="p"
        )[0]
        assert page["orientation"] == 0

    def test_orientation_detection_can_be_disabled(
        self, paddle_service, png_bytes, monkeypatch
    ):
        monkeypatch.setattr(settings, "DETECT_ORIENTATION", False)
        paddle_service.fake_classifier.label = "90"
        page = paddle_service.parse_file(
            "scan.png", "image/png", png_bytes, key_prefix="p"
        )[0]
        assert page["orientation"] == 0
        assert page["content"] == "Marie Curie"


def test_upright_png_undoes_a_clockwise_rotation(png_bytes):
    from app.imaging import upright_png
    from PIL import Image, ImageChops

    with Image.open(io.BytesIO(png_bytes)) as original:
        original = original.convert("RGB")
        buf = io.BytesIO()
        original.rotate(-270, expand=True).save(buf, format="PNG")
    fixed = Image.open(io.BytesIO(upright_png(buf.getvalue(), 270))).convert("RGB")
    assert ImageChops.difference(original, fixed).getbbox() is None
