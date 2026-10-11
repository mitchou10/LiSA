"""Tests for the classification service (a fake classifier stands in for the model)."""

from __future__ import annotations

import pytest
from app.classifiers import BACKENDS, Gliner2Classifier, get_classifier
from app.config import Settings, settings
from app.errors import ClassificationError
from app.schemas import ClassificationInput, ClassificationTask
from app.service import ClassificationService


class FakeClassifier:
    """Answers from a table: ``{(task name, keyword in text): labels}``."""

    name = "fake:test"

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls: list[tuple[str, str]] = []

    def classify(self, text, task):
        self.calls.append((task.name, text))
        for (name, keyword), labels in self.answers.items():
            if name == task.name and keyword in text:
                return labels
        return []


@pytest.fixture
def fake():
    return FakeClassifier(
        {
            ("doc_type", "invoice"): ["invoice"],
            ("doc_type", "contract"): ["contract"],
            ("topics", "invoice"): ["finance", "legal"],
        }
    )


@pytest.fixture
def service(fake, mocker):
    mocker.patch.object(ClassificationService, "update_task")
    svc = ClassificationService.__new__(ClassificationService)
    svc._classifier = fake
    svc.update_task = mocker.Mock()
    return svc


TASKS = [
    {"name": "doc_type", "labels": ["invoice", "contract", "other"]},
    {"name": "topics", "labels": ["finance", "legal", "health"], "multi_label": True},
]


class TestProcess:
    def test_labels_every_page_for_every_task(self, service):
        result = service.process(
            {
                "pages": [
                    {"page_number": 1, "content": "an invoice"},
                    {"page_number": 2, "content": "a contract"},
                ],
                "classifications": TASKS,
            }
        )
        assert result["model"] == "fake:test"
        first, second = result["pages"]
        assert first["page_number"] == 1
        assert first["classifications"] == [
            {"name": "doc_type", "multi_label": False, "labels": ["invoice"]},
            {"name": "topics", "multi_label": True, "labels": ["finance", "legal"]},
        ]
        assert second["classifications"][0]["labels"] == ["contract"]
        assert second["classifications"][1]["labels"] == []

    def test_accepts_the_full_parser_output(self, service):
        page = {
            "page_number": 1,
            "filename": "a.pdf",
            "content": "invoice",
            "width": 595,
            "height": 842,
            "words": [{"text": "invoice", "x": 0.1, "model": "liteparse"}],
            "s3_key": "pages/t/1/1.png",
        }
        result = service.process({"pages": [page], "classifications": TASKS[:1]})
        assert result["pages"][0]["classifications"][0]["labels"] == ["invoice"]

    def test_blank_page_has_no_labels_and_no_model_call(self, service, fake):
        result = service.process(
            {"pages": [{"content": "  \n "}], "classifications": TASKS}
        )
        assert all(c["labels"] == [] for c in result["pages"][0]["classifications"])
        assert fake.calls == []

    def test_labels_outside_the_request_are_dropped(self, service, fake):
        fake.answers[("doc_type", "weird")] = ["not-a-label", "invoice"]
        result = service.process(
            {"pages": [{"content": "weird"}], "classifications": TASKS[:1]}
        )
        assert result["pages"][0]["classifications"][0]["labels"] == ["invoice"]

    def test_reports_progress_and_success(self, service):
        service.process(
            {"pages": [{"content": "invoice"}], "classifications": TASKS},
            task_id="t1",
        )
        statuses = [c.kwargs.get("status") for c in service.update_task.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            (None, "No page"),
            ({"pages": [{"content": "x"}]}, "No classification"),
            ({"classifications": TASKS}, "No page"),
            (
                {"pages": [{"content": "x"}], "classifications": [{"name": "a"}]},
                "Invalid",
            ),
        ],
    )
    def test_rejects_bad_input_and_marks_the_task_failed(
        self, service, payload, message
    ):
        with pytest.raises(ClassificationError, match=message):
            service.process(payload, task_id="t2")
        assert service.update_task.call_args.kwargs["status"] == "error"


class TestSchemas:
    def test_labels_must_be_unique_and_not_empty(self):
        with pytest.raises(ValueError):
            ClassificationTask(name="a", labels=["x", "x"])
        with pytest.raises(ValueError):
            ClassificationTask(name="a", labels=[])

    def test_task_names_must_be_unique(self):
        with pytest.raises(ValueError, match="unique"):
            ClassificationInput(
                classifications=[
                    {"name": "a", "labels": ["x"]},
                    {"name": "a", "labels": ["y"]},
                ]
            )

    def test_threshold_is_a_fraction(self):
        with pytest.raises(ValueError):
            ClassificationTask(name="a", labels=["x"], multi_label=True, threshold=4)


class TestLabelDescriptions:
    def test_bare_strings_and_described_labels_can_be_mixed(self):
        task = ClassificationTask(
            name="t",
            labels=["a", {"name": "b", "description": "the b one"}],
        )
        assert task.label_names == ["a", "b"]
        assert [lb.description for lb in task.labels] == [None, "the b one"]

    def test_duplicate_names_are_rejected_whatever_the_form(self):
        with pytest.raises(ValueError, match="Duplicate"):
            ClassificationTask(
                name="t", labels=["a", {"name": "a", "description": "again"}]
            )

    def test_label_name_is_required(self):
        with pytest.raises(ValueError):
            ClassificationTask(name="t", labels=[{"description": "no name"}])

    def test_descriptions_go_to_gliner2_as_a_mapping(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {"doc_type": "invoice"}
        clf = Gliner2Classifier("m")
        clf._model = model
        task = ClassificationTask(
            name="doc_type",
            labels=[
                {"name": "invoice", "description": "A bill asking for payment"},
                "other",
            ],
        )
        assert clf.classify("text", task) == ["invoice"]
        # A label without description falls back to its own name.
        args = model.classify_text_long.call_args.args
        assert args == (
            "text",
            {"doc_type": {"invoice": "A bill asking for payment", "other": "other"}},
        )

    def test_descriptions_with_multi_label(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {"t": ["a"]}
        clf = Gliner2Classifier("m")
        clf._model = model
        task = ClassificationTask(
            name="t",
            labels=[{"name": "a", "description": "about a"}],
            multi_label=True,
            threshold=0.6,
        )
        clf.classify("x", task)
        assert model.classify_text_long.call_args.args[1] == {
            "t": {"labels": {"a": "about a"}, "multi_label": True, "cls_threshold": 0.6}
        }

    def test_the_service_accepts_described_labels(self, service):
        result = service.process(
            {
                "pages": [{"content": "an invoice"}],
                "classifications": [
                    {
                        "name": "doc_type",
                        "labels": [
                            {"name": "invoice", "description": "A bill"},
                            {"name": "contract", "description": "A signed agreement"},
                        ],
                    }
                ],
            }
        )
        assert result["pages"][0]["classifications"][0]["labels"] == ["invoice"]


class TestLongContext:
    def _clf(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {"t": ["a"]}
        clf = Gliner2Classifier("m")
        clf._model = model
        return clf, model

    def test_pages_are_read_in_full_with_the_long_context_api(self, mocker):
        clf, model = self._clf(mocker)
        text = "word " * 5000
        clf.classify(text, ClassificationTask(name="t", labels=["a", "b"]))
        model.classify_text.assert_not_called()  # no truncating window
        args, kwargs = model.classify_text_long.call_args
        assert args[0] == text  # the whole page, never cut by the service
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (384, 64)

    def test_window_size_and_overlap_come_from_the_settings(self, mocker, monkeypatch):
        monkeypatch.setattr(settings, "CLASSIFIER_CHUNK_SIZE", 512)
        monkeypatch.setattr(settings, "CLASSIFIER_CHUNK_OVERLAP", 128)
        clf, model = self._clf(mocker)
        clf.classify("x", ClassificationTask(name="t", labels=["a"]))
        kwargs = model.classify_text_long.call_args.kwargs
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (512, 128)

    def test_overlap_must_be_smaller_than_the_window(self):
        with pytest.raises(ValueError, match="OVERLAP"):
            Settings(CLASSIFIER_CHUNK_SIZE=100, CLASSIFIER_CHUNK_OVERLAP=100)
        with pytest.raises(ValueError, match="OVERLAP"):
            Settings(CLASSIFIER_CHUNK_OVERLAP=-1)

    def test_the_service_sends_a_long_page_in_one_call(self, service, fake):
        text = "invoice " + "filler " * 20000
        service.process({"pages": [{"content": text}], "classifications": TASKS[:1]})
        assert [len(t) for _, t in fake.calls] == [len(text)]


class TestBackends:
    def test_default_backend_is_gliner2(self):
        assert BACKENDS["gliner2"] is Gliner2Classifier
        assert isinstance(get_classifier(), Gliner2Classifier)

    def test_unknown_backend_is_a_clear_error(self):
        with pytest.raises(ClassificationError, match="nope"):
            get_classifier("nope")

    def test_a_new_backend_plugs_in_without_touching_the_service(
        self, monkeypatch, mocker
    ):
        monkeypatch.setitem(BACKENDS, "fake", FakeClassifier)
        monkeypatch.setattr(settings, "CLASSIFIER_BACKEND", "fake")
        mocker.patch.object(ClassificationService, "update_task")
        svc = ClassificationService.__new__(ClassificationService)
        svc._classifier = None
        assert svc.classifier.name == "fake:test"

    def test_gliner2_single_label_schema_and_result(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {"doc_type": "invoice"}
        clf = Gliner2Classifier("m")
        clf._model = model
        task = ClassificationTask(name="doc_type", labels=["invoice", "other"])
        assert clf.classify("text", task) == ["invoice"]
        assert model.classify_text_long.call_args.args == (
            "text",
            {"doc_type": ["invoice", "other"]},
        )
        assert clf.name == "gliner2:m"

    def test_gliner2_multi_label_schema_threshold_and_result(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {"topics": ["health", "legal"]}
        clf = Gliner2Classifier("m")
        clf._model = model
        task = ClassificationTask(
            name="topics", labels=["health", "legal"], multi_label=True, threshold=0.7
        )
        assert clf.classify("text", task) == ["health", "legal"]
        schema = model.classify_text_long.call_args.args[1]
        assert schema == {
            "topics": {
                "labels": ["health", "legal"],
                "multi_label": True,
                "cls_threshold": 0.7,
            }
        }

    def test_gliner2_multi_label_uses_the_default_threshold(self, mocker, monkeypatch):
        monkeypatch.setattr(settings, "CLASSIFIER_THRESHOLD", 0.55)
        model = mocker.Mock()
        model.classify_text_long.return_value = {"t": []}
        clf = Gliner2Classifier("m")
        clf._model = model
        clf.classify("x", ClassificationTask(name="t", labels=["a"], multi_label=True))
        assert model.classify_text_long.call_args.args[1]["t"]["cls_threshold"] == 0.55

    def test_gliner2_missing_result_means_no_label(self, mocker):
        model = mocker.Mock()
        model.classify_text_long.return_value = {}
        clf = Gliner2Classifier("m")
        clf._model = model
        assert clf.classify("x", ClassificationTask(name="t", labels=["a"])) == []


def test_settings_celery_urls_default_to_redis(monkeypatch):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    cfg = Settings(REDIS_URL="redis://r:6379/1")
    assert cfg.CELERY_BROKER_URL == cfg.CELERY_RESULT_BACKEND == "redis://r:6379/1"
