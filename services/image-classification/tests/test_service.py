"""Tests for the image classification service (a fake model, a fake bucket)."""

from __future__ import annotations

import io

import pytest
from app.classifiers import BACKENDS, ClipClassifier, _embedding, get_classifier
from app.config import Settings, settings
from app.errors import ImageClassificationError
from app.schemas import ClassificationTask, ImageClassificationInput
from app.service import ImageClassificationService, to_result
from app.storage import Storage
from botocore.exceptions import ClientError
from PIL import Image


def png(color="white", size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


class FakeS3:
    """In-memory bucket."""

    def __init__(self, objects=None):
        self.objects = objects or {}
        self.reads: list[str] = []

    def get_object(self, Bucket, Key):
        self.reads.append(Key)
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}


class FakeClassifier:
    """Probabilities from a table ``{image color: {label: p}}``; evenly otherwise."""

    name = "fake:test"

    def __init__(self, table=None):
        self.table = table or {}
        self.calls: list[tuple[str, tuple]] = []

    def classify(self, image, task):
        color = image.getpixel((0, 0))
        self.calls.append((task.name, color))
        names = task.label_names
        probs = self.table.get(color) or {n: 1 / len(names) for n in names}
        return {n: probs.get(n, 0.0) for n in names}


RED, BLUE = (255, 0, 0), (0, 0, 255)
SHAPES = {"name": "shape", "labels": ["square", "circle", "other"]}
TOPICS = {
    "name": "topics",
    "multi_label": True,
    "threshold": 0.3,
    "labels": ["a", "b", "c"],
}


@pytest.fixture(autouse=True)
def bucket(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET", "lisa-files")


@pytest.fixture
def s3():
    return FakeS3(
        {"red.png": png("red"), "blue.png": png("blue"), "page.png": png("red")}
    )


@pytest.fixture
def fake():
    return FakeClassifier(
        {
            RED: {
                "square": 0.8,
                "circle": 0.15,
                "other": 0.05,
                "a": 0.6,
                "b": 0.35,
                "c": 0.05,
            },
            BLUE: {
                "square": 0.1,
                "circle": 0.7,
                "other": 0.2,
                "a": 0.1,
                "b": 0.2,
                "c": 0.7,
            },
        }
    )


@pytest.fixture
def service(fake, s3, mocker):
    svc = ImageClassificationService(classifier=fake, storage=Storage(client=s3))
    svc.update_task = mocker.Mock()
    return svc


class TestToResult:
    def test_single_label_is_the_best_one(self):
        task = ClassificationTask(**SHAPES)
        r = to_result(task, {"square": 0.1, "circle": 0.7, "other": 0.2})
        assert r.labels == ["circle"] and r.scores == {"circle": 0.7}
        assert r.probabilities == {"square": 0.1, "circle": 0.7, "other": 0.2}

    def test_multi_label_keeps_what_reaches_the_threshold_best_first(self):
        task = ClassificationTask(**TOPICS)
        r = to_result(task, {"a": 0.35, "b": 0.6, "c": 0.05})
        assert r.labels == ["b", "a"]
        assert r.scores == {"b": 0.6, "a": 0.35}

    def test_multi_label_can_return_nothing(self):
        task = ClassificationTask(**TOPICS)
        assert to_result(task, {"a": 0.2, "b": 0.2, "c": 0.6}).labels == ["c"]
        task = ClassificationTask(
            name="t", labels=["a", "b", "c", "d"], multi_label=True, threshold=0.9
        )
        assert to_result(task, {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}).labels == []

    def test_the_default_threshold_comes_from_the_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "IMAGE_THRESHOLD", 0.5)
        task = ClassificationTask(name="t", labels=["a", "b"], multi_label=True)
        assert to_result(task, {"a": 0.45, "b": 0.55}).labels == ["b"]


class TestProcess:
    def test_classifies_images_and_the_parser_pages(self, service, fake):
        out = service.process(
            {
                "images": [{"s3_key": "blue.png"}],
                "pages": [
                    {
                        "page_number": 1,
                        "s3_key": "page.png",
                        "content": "ignored",
                        "words": [],
                    },
                    {"page_number": 2, "s3_key": None},  # no screenshot: skipped
                ],
                "classifications": [SHAPES, TOPICS],
            }
        )
        assert out["model"] == "fake:test"
        blue, page = out["images"]
        assert blue["s3_key"] == "blue.png" and blue["page_number"] is None
        assert page["s3_key"] == "page.png" and page["page_number"] == 1
        shape, topics = page["classifications"]
        assert shape["labels"] == ["square"] and shape["scores"] == {"square": 0.8}
        assert topics["labels"] == ["a", "b"]
        assert blue["classifications"][0]["labels"] == ["circle"]
        assert blue["classifications"][1]["labels"] == ["c"]

    def test_every_classification_runs_on_every_image(self, service, fake):
        service.process(
            {
                "images": [{"s3_key": "red.png"}, {"s3_key": "blue.png"}],
                "classifications": [SHAPES, TOPICS],
            }
        )
        assert len(fake.calls) == 4

    def test_reports_progress_and_success(self, service):
        service.process(
            {"images": [{"s3_key": "red.png"}], "classifications": [SHAPES]},
            task_id="t1",
        )
        statuses = [c.kwargs.get("status") for c in service.update_task.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            (None, "No image"),
            ({"images": [{"s3_key": "red.png"}]}, "No classification"),
            ({"pages": [{"page_number": 1}], "classifications": [SHAPES]}, "No image"),
            (
                {
                    "images": [{"s3_key": "red.png"}],
                    "classifications": [{"name": "x", "labels": ["only"]}],
                },
                "Invalid",
            ),
            (
                {
                    "images": [{"s3_key": "red.png"}],
                    "classifications": [SHAPES, SHAPES],
                },
                "unique",
            ),
        ],
    )
    def test_bad_input_fails_the_task(self, service, payload, message):
        with pytest.raises(ImageClassificationError, match=message):
            service.process(payload, task_id="t")
        assert service.update_task.call_args.kwargs["status"] == "error"

    def test_a_missing_image_fails_the_task(self, service):
        with pytest.raises(ImageClassificationError, match="Cannot fetch"):
            service.process(
                {"images": [{"s3_key": "nope.png"}], "classifications": [SHAPES]}
            )

    def test_something_that_is_not_an_image_fails_the_task(self, service, s3):
        s3.objects["notes.txt"] = b"plain text"
        with pytest.raises(ImageClassificationError, match="not an image"):
            service.process(
                {"images": [{"s3_key": "notes.txt"}], "classifications": [SHAPES]}
            )

    def test_a_huge_image_is_refused(self, service, monkeypatch):
        monkeypatch.setattr(settings, "MAX_IMAGE_MB", 0.00001)
        with pytest.raises(ImageClassificationError, match="limit"):
            service.process(
                {"images": [{"s3_key": "red.png"}], "classifications": [SHAPES]}
            )

    def test_the_bucket_is_checked_before_reading(self, service, s3, monkeypatch):
        monkeypatch.setattr(settings, "S3_BUCKET", "")
        with pytest.raises(ImageClassificationError, match="S3_BUCKET"):
            service.process(
                {"images": [{"s3_key": "red.png"}], "classifications": [SHAPES]}
            )
        assert s3.reads == []


class TestSchemas:
    def test_a_classification_needs_two_labels(self):
        with pytest.raises(ValueError):
            ClassificationTask(name="t", labels=["only"])

    def test_labels_are_unique(self):
        with pytest.raises(ValueError, match="Duplicate"):
            ClassificationTask(
                name="t", labels=["a", {"name": "a", "description": "again"}]
            )

    def test_bare_strings_and_described_labels_mix(self):
        task = ClassificationTask(
            name="t", labels=["a", {"name": "b", "description": "a blue circle"}]
        )
        assert task.label_names == ["a", "b"]

    def test_pages_without_screenshot_are_dropped_at_validation(self):
        data = ImageClassificationInput(
            pages=[
                {"page_number": 1, "s3_key": "k"},
                {"page_number": 2},
                {"s3_key": ""},
            ]
        )
        assert [p.s3_key for p in data.pages] == ["k"]


class TestClip:
    def test_a_description_is_matched_as_is_a_bare_label_uses_the_template(self):
        task = ClassificationTask(
            name="t",
            labels=[{"name": "invoice", "description": "a scanned invoice"}, "cat"],
        )
        assert ClipClassifier.prompts(task) == ["a scanned invoice", "a photo of cat"]

    def test_the_template_is_configurable(self, monkeypatch):
        monkeypatch.setattr(settings, "IMAGE_PROMPT_TEMPLATE", "a scan of {label}")
        task = ClassificationTask(name="t", labels=["a form", "a receipt"])
        assert ClipClassifier.prompts(task) == [
            "a scan of a form",
            "a scan of a receipt",
        ]

    def test_the_embedding_is_unwrapped_whatever_the_transformers_version(self):
        class Tensor:
            def norm(self):  # looks like a tensor
                return 1

        class Wrapped:
            pooler_output = "embedding"

        tensor = Tensor()
        assert _embedding(tensor) is tensor
        assert _embedding(Wrapped()) == "embedding"

    def test_the_model_name_is_reported_without_loading_it(self):
        clf = ClipClassifier("some/clip")
        assert clf.name == "clip:some/clip" and clf._model is None

    def test_default_backend_and_model(self):
        assert BACKENDS["clip"] is ClipClassifier
        assert get_classifier().name == f"clip:{settings.IMAGE_MODEL}"
        assert settings.IMAGE_MODEL == "openai/clip-vit-base-patch32"

    def test_unknown_backend(self):
        with pytest.raises(ImageClassificationError, match="nope"):
            get_classifier("nope")

    def test_a_new_backend_plugs_in(self, monkeypatch):
        monkeypatch.setitem(BACKENDS, "fake", FakeClassifier)
        monkeypatch.setattr(settings, "IMAGE_BACKEND", "fake")
        svc = ImageClassificationService(storage=Storage(client=FakeS3()))
        assert svc.classifier.name == "fake:test"


def test_celery_urls_default_to_redis(monkeypatch):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    cfg = Settings(REDIS_URL="redis://r:6379/1")
    assert cfg.CELERY_BROKER_URL == cfg.CELERY_RESULT_BACKEND == "redis://r:6379/1"
