import pytest
from app.service import AnonymizeServiceV2, Span, redact
from pydantic import ValidationError


@pytest.fixture
def service(mocker):
    mocker.patch("app.service.BaseService.__init__", return_value=None)
    svc = AnonymizeServiceV2()
    svc._tasks = mocker.Mock()
    return svc


def test_redact_marks_spans_only_when_not_blurred():
    text = "Hello John Doe, bye"
    out = redact(
        text, [Span(start=6, end=14, text="John Doe", label="person")], blurred=False
    )
    assert out == "Hello [PERSON], bye"


def test_redact_blurred_stars_everything_but_keeps_span_markers():
    text = "Hello John Doe,\nbye"
    out = redact(
        text, [Span(start=6, end=14, text="John Doe", label="person")], blurred=True
    )
    assert out == "***** [PERSON]*\n***"


def test_redact_blurred_keeps_whitespace():
    assert redact("ab cd\nef", [], blurred=True) == "** **\n**"


def test_redact_applies_every_span_whatever_their_order():
    text = "aa bb cc"
    spans = [
        Span(start=0, end=2, text="aa", label="name"),
        Span(start=6, end=8, text="cc", label="email"),
    ]
    expected = "[NAME] bb [EMAIL]"
    assert redact(text, spans, blurred=False) == expected
    assert redact(text, spans[::-1], blurred=False) == expected
    assert redact(text, spans, blurred=True) == "[NAME] ** [EMAIL]"


def test_redact_clips_overlap_and_ignores_out_of_range():
    text = "abcdef"
    spans = [
        Span(start=0, end=4, text="abcd", label="a"),
        Span(start=2, end=6, text="cdef", label="b"),
        Span(start=50, end=60, text="", label="x"),
    ]
    assert redact(text, spans, blurred=False) == "[A][B]"


def test_process_redacts_pages_and_reports(service, mocker):
    update = mocker.patch.object(service, "update_task")
    result = service.process(
        {
            "pages": [{"content": "Hello John", "page_number": 1}],
            "anonymized_pages": [
                {
                    "page_number": 1,
                    "span": [
                        {"start": 6, "end": 10, "text": "John", "label": "person"}
                    ],
                }
            ],
            "blurred": True,
        },
        task_id="t1",
    )
    assert result["pages"][0]["content"] == "***** [PERSON]"
    statuses = [c.kwargs.get("status") for c in update.call_args_list]
    assert statuses[0] == "running" and statuses[-1] == "success"


def test_process_marks_task_failed_on_bad_input(service, mocker):
    update = mocker.patch.object(service, "update_task")
    with pytest.raises(ValidationError):
        service.process({"pages": "nope"}, task_id="t2")
    assert update.call_args.kwargs["status"] == "error"


def test_definition_is_registrable(service):
    assert service.type in {"guard", "analyser", "other"}
    assert service.input_schema["properties"]["pages"]


def _png(size=(200, 100)):
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    for x in range(0, size[0], 4):
        d.line((x, 0, x, size[1]), fill="black", width=1)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_parse_s3_location():
    from app.service import parse_s3_location

    assert parse_s3_location("s3://b/pages/1.png", "") == ("b", "pages/1.png")
    assert parse_s3_location("http://rustfs:9000/b/pages/1.png?X=1", "b") == (
        "b",
        "pages/1.png",
    )
    with pytest.raises(ValueError):
        parse_s3_location("ftp://x/y", "b")


def test_blur_and_annotate_blurs_and_draws_label():
    import io

    from app.service import Bbox, blur_and_annotate
    from PIL import Image

    data, mime = blur_and_annotate(
        _png(), [Bbox(x=0.1, y=0.3, width=0.3, height=0.2, label="PERSON")]
    )
    assert mime == "image/png"
    out = Image.open(io.BytesIO(data)).convert("RGB")
    assert out.size == (200, 100)
    # Stripes are gone away from the box (blurred to near-uniform grey)...
    far = [out.getpixel((150, y))[0] for y in range(60, 100)]
    assert max(far) - min(far) < 60
    # ...and the box outline is drawn in red.
    assert out.getpixel((20, 30)) == (220, 38, 38)


def test_process_replaces_page_image_in_s3(service, mocker):
    s3 = mocker.Mock()
    s3.get_object.return_value = {"Body": mocker.Mock(read=lambda: _png((200, 100)))}
    service._s3 = s3
    mocker.patch.object(service, "update_task")
    service.process(
        {
            "pages": [
                {
                    "content": "Hello John",
                    "page_number": 1,
                    "page_url": "s3://lisa/pages/p1.png",
                }
            ],
            "anonymized_pages": [
                {
                    "page_number": 1,
                    "span": [
                        {"start": 6, "end": 10, "text": "John", "label": "person"}
                    ],
                    "bboxes": [
                        {
                            "x": 0.1,
                            "y": 0.1,
                            "width": 0.2,
                            "height": 0.1,
                            "label": "PERSON",
                        }
                    ],
                }
            ],
            "blurred": True,
        },
        task_id="t5",
    )
    s3.get_object.assert_called_once_with(Bucket="lisa", Key="pages/p1.png")
    kwargs = s3.put_object.call_args.kwargs
    assert (kwargs["Bucket"], kwargs["Key"]) == ("lisa", "pages/p1.png")
    assert kwargs["ContentType"] == "image/png"
    assert kwargs["Body"] != _png((200, 100))


def test_images_untouched_when_not_blurred(service, mocker):
    s3 = mocker.Mock()
    service._s3 = s3
    mocker.patch.object(service, "update_task")
    service.process(
        {
            "pages": [{"content": "x", "page_number": 1, "page_url": "s3://b/k.png"}],
            "anonymized_pages": [
                {
                    "page_number": 1,
                    "bboxes": [
                        {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1, "label": "L"}
                    ],
                }
            ],
        }
    )
    s3.get_object.assert_not_called()
    s3.put_object.assert_not_called()


def test_bbox_must_be_relative():
    from app.service import Bbox
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Bbox(x=120, y=0.1, width=0.1, height=0.1, label="L")
