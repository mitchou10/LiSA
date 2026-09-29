"""Tests for ParserService (runs the real LiteParse on generated documents)."""

from __future__ import annotations

import pytest
from conftest import b64

from app import config
from app.service import ParserError, ParserService, _decode, _suffix, blur_png, build_page


@pytest.fixture
def service():
    return ParserService()


def _assert_offsets_match(page):
    """Every word's start/end must slice its text out of the page content."""
    assert page["words"], "expected word boxes"
    for w in page["words"]:
        assert page["content"][w["start"] : w["end"]] == w["text"]
    for line in page["lines"]:
        assert page["content"][line["start"] : line["end"]] == line["text"]


class TestHelpers:
    def test_decode_plain_and_data_url(self):
        assert _decode("aGk=") == b"hi"
        assert _decode("data:text/plain;base64,aGk=") == b"hi"

    def test_decode_rejects_garbage(self):
        with pytest.raises(ParserError):
            _decode("not base64!!")

    def test_suffix_from_name_then_mime(self):
        assert _suffix("Scan.PNG", None) == ".png"
        assert _suffix("noext", "application/pdf") == ".pdf"
        assert _suffix("noext", None) == ""


class TestPdf:
    def test_native_text_and_word_boxes(self, service, pdf_bytes):
        pages = service.parse_file("doc.pdf", "application/pdf", pdf_bytes)
        assert len(pages) == 2
        first = pages[0]
        assert "john@example.com" in first["content"]
        assert first["width"] > 0 and first["height"] > 0
        assert first["image"].startswith("data:image/png;base64,")
        _assert_offsets_match(first)
        email = next(w for w in first["words"] if w["text"] == "john@example.com")
        assert 0 <= email["x"] < first["width"]
        assert 0 <= email["y"] < first["height"]

    def test_entity_offsets_map_to_boxes(self, service, pdf_bytes):
        """An analyser's start_char/end_char selects the matching word boxes."""
        page = service.parse_file("doc.pdf", None, pdf_bytes)[0]
        start = page["content"].index("john@example.com")
        end = start + len("john@example.com")
        hit = [w for w in page["words"] if w["start"] < end and w["end"] > start]
        assert [w["text"] for w in hit] == ["john@example.com"]


class TestImageOcr:
    def test_ocr_text_and_proportional_words(self, service, png_bytes):
        try:
            pages = service.parse_file("scan.png", "image/png", png_bytes)
        except ParserError as exc:  # tessdata download unavailable (offline CI)
            pytest.skip(str(exc))
        page = pages[0]
        assert "Marie Curie" in page["content"]
        _assert_offsets_match(page)
        words = page["words"]
        # Proportional split keeps words ordered left to right inside the line.
        assert [w["x"] for w in words] == sorted(w["x"] for w in words)
        line = page["lines"][0]
        assert all(line["x"] <= w["x"] <= line["x"] + line["width"] for w in words)


class TestProcess:
    def test_process_numbers_pages_across_files(self, service, pdf_bytes):
        result = service.process(
            {
                "files": [
                    {"filename": "a.pdf", "data_base64": b64(pdf_bytes)},
                    {"filename": "b.pdf", "data_base64": b64(pdf_bytes)},
                ]
            }
        )
        assert [p["page_number"] for p in result["pages"]] == [1, 2, 3, 4]
        assert [p["filename"] for p in result["pages"]] == ["a.pdf"] * 2 + ["b.pdf"] * 2
        assert result["error"] is None

    def test_process_reports_progress_and_scrubs_input(self, service, pdf_bytes, mocker):
        update = mocker.patch.object(service, "update_task")
        scrub = mocker.patch.object(service._tasks, "update")
        service.process(
            {"files": [{"filename": "a.pdf", "data_base64": b64(pdf_bytes)}]},
            task_id="t1",
        )
        statuses = [c.kwargs.get("status") for c in update.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"
        # The uploaded bytes are removed from the stored task.
        scrub.assert_called_once_with(
            "t1", {"input_data": {"files": [{"filename": "a.pdf", "mime": None}]}}
        )

    @pytest.mark.parametrize("payload", [None, {}, {"files": []}])
    def test_process_requires_files(self, service, payload):
        with pytest.raises(ParserError, match="No file"):
            service.process(payload)

    def test_process_marks_task_failed_on_bad_file(self, service, mocker):
        update = mocker.patch.object(service, "update_task")
        mocker.patch.object(service._tasks, "update")
        with pytest.raises(ParserError):
            service.process(
                {"files": [{"filename": "x.txt", "data_base64": b64(b"plain text")}]},
                task_id="t2",
            )
        assert update.call_args.kwargs["status"] == "error"

    def test_file_size_limit(self, service, monkeypatch):
        monkeypatch.setattr(config, "MAX_FILE_MB", 0.0001)
        with pytest.raises(ParserError, match="limit"):
            service.parse_file("big.pdf", None, b"x" * 1000)


def test_build_page_skips_blank_lines():
    class Item:
        def __init__(self, text):
            self.text, self.x, self.y, self.width, self.height = text, 0, 0, 10, 5
            self.confidence, self.words = None, []

    class Parsed:
        width, height = 100, 100
        text_items = [Item("hello world"), Item("   "), Item("bye")]

    page = build_page(Parsed())
    assert page["content"] == "hello world\nbye"
    assert [w["text"] for w in page["words"]] == ["hello", "world", "bye"]
    _assert_offsets_match(page)


class TestBlur:
    @staticmethod
    def _decode_image(page):
        import base64

        return base64.b64decode(page["image"].split(",", 1)[1])

    def test_blurred_image_is_unreadable_but_boxes_remain(self, service, png_bytes):
        from liteparse import LiteParse

        try:
            clear = service.parse_file("scan.png", "image/png", png_bytes)[0]
        except ParserError as exc:
            pytest.skip(str(exc))
        blurred = service.parse_file("scan.png", "image/png", png_bytes, blur=True)[0]

        assert clear["blurred"] is False and blurred["blurred"] is True
        assert self._decode_image(clear) != self._decode_image(blurred)
        # Text and boxes (used by the overlay) are unchanged...
        assert blurred["content"] == clear["content"]
        assert blurred["words"] == clear["words"]
        # ...but OCR can no longer read the blurred pixels.
        reread = LiteParse(quiet=True, ocr_language=config.OCR_LANGUAGE).parse(
            self._decode_image(blurred)
        )
        assert "Curie" not in reread.text and "Marie" not in reread.text

    def test_blur_keeps_dimensions(self, png_bytes):
        import io

        from PIL import Image

        out = Image.open(io.BytesIO(blur_png(png_bytes)))
        assert out.size == Image.open(io.BytesIO(png_bytes)).size

    def test_process_forwards_blur_flag(self, service, pdf_bytes):
        files = [{"filename": "a.pdf", "data_base64": b64(pdf_bytes)}]
        clear = service.process({"files": files})["pages"][0]
        blurred = service.process({"files": files, "blur_screenshots": True})["pages"][0]
        assert (clear["blurred"], blurred["blurred"]) == (False, True)
        assert clear["image"] != blurred["image"]
