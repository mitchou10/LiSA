"""Tests for the relation extraction service (a fake extractor stands in for the model)."""

from __future__ import annotations

import pytest
from app.boxes import boxes_for_span
from app.config import Settings, settings
from app.defaults import DEFAULT_RELATIONS
from app.errors import RelationError
from app.extractors import (
    BACKENDS,
    Gliner2Extractor,
    RawEndpoint,
    RawRelation,
    get_extractor,
    parse_relations,
)
from app.schemas import InputWord, RelationRule
from app.service import RelationService


class FakeExtractor:
    name = "fake:test"

    def __init__(self, found=()):
        self.found = list(found)
        self.calls: list[tuple[str, list[RelationRule], float]] = []

    def extract(self, text, rules, threshold):
        self.calls.append((text, rules, threshold))
        return self.found


def rel(name, head, tail, h_score=0.9, t_score=0.9):
    """A raw relation from (text, start, end) triples."""
    return RawRelation(
        relation=name,
        head=RawEndpoint(head[0], head[1], head[2], h_score),
        tail=RawEndpoint(tail[0], tail[1], tail[2], t_score),
    )


@pytest.fixture
def fake():
    return FakeExtractor()


@pytest.fixture
def service(fake, mocker):
    svc = RelationService(extractor=fake)
    svc.update_task = mocker.Mock()
    return svc


TEXT = "Tim Cook works for Apple Inc. in Cupertino"
WORKS_FOR = rel("works_for", ("Tim Cook", 0, 8), ("Apple Inc.", 19, 29))


def run(service, text=TEXT, **extra):
    return service.process({"pages": [{"page_number": 1, "content": text}], **extra})


class TestRelations:
    def test_both_ends_keep_their_offsets_and_the_model(self, service, fake):
        fake.found = [WORKS_FOR]
        out = run(service)
        (r,) = out["pages"][0]["relations"]
        assert (r["id"], r["relation"]) == ("r0", "works_for")
        for end in (r["head"], r["tail"]):
            assert TEXT[end["start"] : end["end"]] == end["text"]
        assert (r["head"]["text"], r["tail"]["text"]) == ("Tim Cook", "Apple Inc.")
        assert r["model"] == "fake:test" == out["model"]

    def test_the_score_is_the_weakest_end(self, service, fake):
        fake.found = [rel("works_for", ("a", 0, 1), ("b", 2, 3), 0.99, 0.7)]
        (r,) = run(service, "a b")["pages"][0]["relations"]
        assert r["score"] == 0.7

    def test_reading_order_of_the_head(self, service, fake):
        fake.found = [
            rel("works_for", ("late", 20, 24), ("x", 30, 31)),
            rel("works_for", ("early", 0, 5), ("y", 6, 7)),
        ]
        heads = [r["head"]["text"] for r in run(service)["pages"][0]["relations"]]
        assert heads == ["early", "late"]

    def test_no_relation(self, service):
        assert run(service)["pages"][0]["relations"] == []

    def test_relation_types_that_were_not_asked_are_dropped(self, service, fake):
        fake.found = [rel("mystery", ("a", 0, 1), ("b", 2, 3))]
        assert run(service)["pages"][0]["relations"] == []

    def test_a_weak_relation_is_dropped_by_the_global_threshold(self, service, fake):
        fake.found = [rel("works_for", ("a", 0, 1), ("b", 2, 3), 0.99, 0.4)]
        assert run(service)["pages"][0]["relations"] == []

    def test_a_relation_threshold_overrides_the_global_one(self, service, fake):
        rules = [{"name": "works_for", "threshold": 0.95}]
        fake.found = [rel("works_for", ("a", 0, 1), ("b", 2, 3), 0.9, 0.9)]
        assert run(service, "a b", relations=rules)["pages"][0]["relations"] == []
        fake.found = [rel("works_for", ("a", 0, 1), ("b", 2, 3), 0.97, 0.99)]
        assert len(run(service, "a b", relations=rules)["pages"][0]["relations"]) == 1

    def test_boxes_for_both_ends_when_the_page_has_words(self, service, fake):
        words = [
            {"x": 0.1, "y": 0.1, "width": 0.15, "height": 0.02, "start": 0, "end": 8},
            {"x": 0.5, "y": 0.3, "width": 0.2, "height": 0.02, "start": 19, "end": 29},
        ]
        fake.found = [WORKS_FOR]
        out = service.process({"pages": [{"content": TEXT, "words": words}]})
        (r,) = out["pages"][0]["relations"]
        (head_box,) = r["head"]["bboxes"]
        (tail_box,) = r["tail"]["bboxes"]
        assert head_box["x"] == pytest.approx(0.1) and tail_box["y"] == pytest.approx(
            0.3
        )

    def test_no_boxes_without_words(self, service, fake):
        fake.found = [WORKS_FOR]
        (r,) = run(service)["pages"][0]["relations"]
        assert r["head"]["bboxes"] == [] and r["tail"]["bboxes"] == []

    def test_the_parser_pages_are_accepted_as_they_are(self, service):
        page = {
            "page_number": 1,
            "filename": "a.pdf",
            "content": "hi",
            "width": 595,
            "lines": [{"text": "hi", "model": "liteparse"}],
            "s3_key": "pages/t/1/1.png",
        }
        assert service.process({"pages": [page]})["pages"][0]["page_number"] == 1


class TestWhatToLookFor:
    def test_defaults_apply_when_nothing_is_given(self, service, fake):
        run(service)
        _, rules, threshold = fake.calls[0]
        assert rules == DEFAULT_RELATIONS and threshold == settings.RELATION_THRESHOLD

    def test_defaults_describe_their_direction(self):
        assert {r.name for r in DEFAULT_RELATIONS} >= {"works_for", "lives_in"}
        assert all(r.description for r in DEFAULT_RELATIONS)

    def test_overrides_replace_the_defaults(self, service, fake):
        run(
            service,
            relations=[
                "owns",
                {"name": "prescribed", "description": "doctor -> patient"},
            ],
            threshold=0.8,
        )
        _, rules, threshold = fake.calls[0]
        assert [(r.name, r.description) for r in rules] == [
            ("owns", None),
            ("prescribed", "doctor -> patient"),
        ]
        assert threshold == 0.8

    def test_blank_pages_are_not_sent_to_the_model(self, service, fake):
        out = run(service, "  \n ")
        assert fake.calls == [] and out["pages"][0]["relations"] == []

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            (None, "No page"),
            ({"pages": [{"content": "x"}], "relations": []}, "Nothing"),
            ({"pages": [{"content": "x"}], "relations": [{"name": ""}]}, "Invalid"),
            ({"pages": [{"content": "x"}], "relations": ["a", "A"]}, "unique"),
            ({"pages": [{"content": "x"}], "threshold": 3}, "Invalid"),
        ],
    )
    def test_bad_input_fails_the_task(self, service, payload, message):
        with pytest.raises(RelationError, match=message):
            service.process(payload, task_id="t1")
        assert service.update_task.call_args.kwargs["status"] == "error"

    def test_reports_progress_and_success(self, service):
        run(service)
        statuses = [c.kwargs.get("status") for c in service.update_task.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"


class TestGliner2Extractor:
    SPAN = {"text": "Tim Cook", "confidence": 0.95, "start": 0, "end": 8}
    RAW = {
        "relation_extraction": {
            "works_for": [
                {
                    "head": SPAN,
                    "tail": {
                        "text": "Apple",
                        "confidence": 0.9,
                        "start": 19,
                        "end": 24,
                    },
                }
            ],
            "lives_in": [],
        }
    }

    def _extractor(self, mocker, raw=None):
        model = mocker.Mock()
        model.extract_long.return_value = self.RAW if raw is None else raw
        ext = Gliner2Extractor("m")
        ext._model = model
        return ext, model

    def test_parse_relations(self):
        (r,) = parse_relations(self.RAW)
        assert r.relation == "works_for"
        assert (r.head.text, r.head.start, r.head.end, r.head.score) == (
            "Tim Cook",
            0,
            8,
            0.95,
        )
        assert (r.tail.text, r.tail.score) == ("Apple", 0.9)

    def test_relations_without_spans_are_ignored(self):
        raw = {"relation_extraction": {"x": [("a", "b"), {"head": {"text": "a"}}]}}
        assert parse_relations(raw) == []
        assert parse_relations({}) == []

    def test_relations_go_as_per_relation_config(self, mocker):
        ext, model = self._extractor(mocker)
        rules = [
            RelationRule(name="works_for", description="Employment", threshold=0.8),
            RelationRule(name="lives_in"),
        ]
        out = ext.extract("text", rules, 0.5)
        schema_builder = model.create_schema.return_value.relations
        assert schema_builder.call_args.args[0] == {
            "works_for": {"description": "Employment", "threshold": 0.8},
            "lives_in": {"description": "lives_in"},
        }
        assert schema_builder.call_args.kwargs["threshold"] == 0.5
        assert [r.relation for r in out] == ["works_for"]

    def test_pages_are_read_in_full_with_the_long_context_api(self, mocker):
        ext, model = self._extractor(mocker)
        text = "word " * 5000
        ext.extract(text, [RelationRule(name="works_for")], 0.5)
        model.extract.assert_not_called()  # no truncating window
        args, kwargs = model.extract_long.call_args
        assert args[0] == text  # the whole page, never cut by the service
        assert kwargs["include_spans"] and kwargs["include_confidence"]
        # A relation needs both ends in one window: wider overlap than for NER.
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (384, 128)

    def test_window_size_and_overlap_come_from_the_settings(self, mocker, monkeypatch):
        monkeypatch.setattr(settings, "CHUNK_SIZE", 512)
        monkeypatch.setattr(settings, "CHUNK_OVERLAP", 200)
        ext, model = self._extractor(mocker, {})
        ext.extract("x", [RelationRule(name="r")], 0.5)
        kwargs = model.extract_long.call_args.kwargs
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (512, 200)

    def test_the_service_sends_a_long_page_in_one_call(self, service, fake):
        text = "Tim Cook works for Apple. " + "filler " * 20000
        run(service, text)
        assert [len(t) for t, _, _ in fake.calls] == [len(text)]


class TestBackendsSettingsAndBoxes:
    def test_default_backend(self):
        assert BACKENDS["gliner2"] is Gliner2Extractor
        assert get_extractor().name == f"gliner2:{settings.RELATION_MODEL}"

    def test_unknown_backend(self):
        with pytest.raises(RelationError, match="nope"):
            get_extractor("nope")

    def test_a_new_backend_plugs_in(self, monkeypatch):
        monkeypatch.setitem(BACKENDS, "fake", FakeExtractor)
        monkeypatch.setattr(settings, "RELATION_BACKEND", "fake")
        svc = RelationService.__new__(RelationService)
        svc._extractor = None
        assert svc.extractor.name == "fake:test"

    def test_overlap_must_be_smaller_than_the_window(self):
        with pytest.raises(ValueError, match="OVERLAP"):
            Settings(CHUNK_SIZE=100, CHUNK_OVERLAP=100)

    def test_celery_urls_default_to_redis(self, monkeypatch):
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
        cfg = Settings(REDIS_URL="redis://r:6379/1")
        assert cfg.CELERY_BROKER_URL == cfg.CELERY_RESULT_BACKEND == "redis://r:6379/1"

    def test_boxes_follow_the_angle_of_the_text(self):
        def w(x, y, start, end, angle):
            return InputWord(
                x=x, y=y, width=0.02, height=0.1, start=start, end=end, angle=angle
            )

        # Text turned 90 degrees reads top to bottom: its words stack along y and
        # share a line when they overlap in x.
        boxes = boxes_for_span(
            [w(0.8, 0.1, 0, 3, 90), w(0.8, 0.3, 4, 7, 90), w(0.5, 0.1, 8, 11, 90)],
            0,
            11,
        )
        assert [b.angle for b in boxes] == [90, 90]
        assert boxes[1].height == pytest.approx(0.3) and boxes[
            1
        ].width == pytest.approx(0.02)

    def test_boxes_one_per_line(self):
        def w(x, y, start, end):
            return InputWord(x=x, y=y, width=0.1, height=0.02, start=start, end=end)

        boxes = boxes_for_span(
            [w(0.1, 0.1, 0, 3), w(0.3, 0.1, 4, 7), w(0.1, 0.2, 8, 11)], 0, 11
        )
        assert len(boxes) == 2 and boxes[0].width == pytest.approx(0.3)
