"""Tests for the NER service (a fake extractor stands in for the model)."""

from __future__ import annotations

import pytest
from app.boxes import boxes_for_span
from app.config import Settings, settings
from app.defaults import DEFAULT_ENTITIES
from app.errors import NerError
from app.extractors import (
    BACKENDS,
    Gliner2Extractor,
    RawEntity,
    get_extractor,
    parse_entities,
)
from app.profile import ProfileProvider
from app.schemas import EntityRule, InputWord
from app.service import NerService


class FakeExtractor:
    name = "fake:test"

    def __init__(self, found=()):
        self.found = list(found)
        self.calls: list[tuple[str, list[EntityRule], float]] = []

    def extract(self, text, rules, threshold):
        self.calls.append((text, rules, threshold))
        return self.found


def entity_rule(label, **kw):
    return {
        "label": label,
        "category": "PII",
        "severity": "medium",
        "action": "redact",
        "enabled": True,
        "threshold": None,
        **kw,
    }


def make_service(mocker, extractor, profile=None, version=7):
    profile = profile or {"threshold": 0.5, "entities": [entity_rule("email")]}
    provider = ProfileProvider(
        service_key="k",
        fallback=lambda: {"version": None, **profile},
        fetch=lambda: (version, profile),
    )
    svc = NerService(extractor=extractor, profile_provider=provider)
    svc.update_task = mocker.Mock()
    return svc


@pytest.fixture
def fake():
    return FakeExtractor()


@pytest.fixture
def service(fake, mocker):
    return make_service(mocker, fake)


def run(service, text="mail a@b.c", **extra):
    return service.process({"pages": [{"page_number": 1, "content": text}], **extra})


class TestEntities:
    def test_entities_carry_offsets_rule_and_model(self, service, fake):
        text = "Mail john@acme.com now"
        fake.found = [RawEntity("email", "john@acme.com", 5, 18, 0.97)]
        out = run(service, text)
        (ent,) = out["pages"][0]["entities"]
        assert text[ent["start"] : ent["end"]] == ent["text"] == "john@acme.com"
        assert ent["id"] == "e0" and ent["label"] == "email"
        assert (ent["category"], ent["severity"], ent["action"]) == (
            "PII",
            "medium",
            "redact",
        )
        assert ent["flagged"] is True and ent["score"] == 0.97
        assert ent["model"] == "fake:test" == out["model"]

    def test_reading_order_and_page_verdict(self, service, fake):
        fake.found = [
            RawEntity("email", "b", 10, 11, 0.9),
            RawEntity("email", "a", 2, 3, 0.9),
        ]
        out = run(service)
        page = out["pages"][0]
        assert [e["text"] for e in page["entities"]] == ["a", "b"]
        assert (page["flagged"], page["severity"], page["action"]) == (
            True,
            "medium",
            "redact",
        )
        assert out["flagged"] is True and out["profile_version"] == 7

    def test_no_entity_means_nothing_flagged(self, service):
        out = run(service)
        page = out["pages"][0]
        assert page["entities"] == [] and page["flagged"] is False
        assert (page["severity"], page["action"]) == (None, "allow")
        assert out["flagged"] is False

    def test_labels_that_were_not_asked_are_dropped(self, service, fake):
        fake.found = [RawEntity("mystery", "x", 0, 1, 0.99)]
        assert run(service)["pages"][0]["entities"] == []

    def test_scores_below_the_threshold_are_dropped(self, service, fake):
        fake.found = [RawEntity("email", "x", 0, 1, 0.49)]
        assert run(service)["pages"][0]["entities"] == []

    def test_a_label_threshold_overrides_the_global_one(self, mocker, fake):
        profile = {
            "threshold": 0.5,
            "entities": [entity_rule("email", threshold=0.9)],
        }
        service = make_service(mocker, fake, profile)
        fake.found = [RawEntity("email", "x", 0, 1, 0.8)]
        assert run(service)["pages"][0]["entities"] == []
        fake.found = [RawEntity("email", "x", 0, 1, 0.95)]
        assert len(run(service)["pages"][0]["entities"]) == 1

    def test_the_highest_severity_and_action_win(self, mocker, fake):
        profile = {
            "threshold": 0.5,
            "entities": [
                entity_rule("low one", severity="low"),
                entity_rule("high one", severity="high", action="block"),
            ],
        }
        service = make_service(mocker, fake, profile)
        fake.found = [
            RawEntity("low one", "a", 0, 1, 0.9),
            RawEntity("high one", "b", 2, 3, 0.9),
        ]
        out = run(service, "a b")
        assert (out["severity"], out["action"]) == ("high", "block")

    def test_allow_entities_are_reported_but_not_flagged(self, mocker, fake):
        profile = {"threshold": 0.5, "entities": [entity_rule("city", action="allow")]}
        service = make_service(mocker, fake, profile)
        fake.found = [RawEntity("city", "Paris", 0, 5, 0.9)]
        out = run(service, "Paris")
        assert out["pages"][0]["entities"][0]["flagged"] is False
        assert out["flagged"] is False and out["action"] == "allow"

    def test_boxes_when_the_page_has_words(self, service, fake):
        text = "Mail john@acme.com now"
        words = [
            {"x": 0.1, "y": 0.1, "width": 0.05, "height": 0.02, "start": 0, "end": 4},
            {"x": 0.2, "y": 0.1, "width": 0.2, "height": 0.02, "start": 5, "end": 18},
        ]
        fake.found = [RawEntity("email", "john@acme.com", 5, 18, 0.99)]
        out = service.process({"pages": [{"content": text, "words": words}]})
        (box,) = out["pages"][0]["entities"][0]["bboxes"]
        assert box == pytest.approx({"x": 0.2, "y": 0.1, "width": 0.2, "height": 0.02})

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
    def test_the_live_profile_drives_the_labels_and_only_enabled_ones(
        self, mocker, fake
    ):
        profile = {
            "threshold": 0.6,
            "entities": [entity_rule("iban"), entity_rule("secret", enabled=False)],
        }
        service = make_service(mocker, fake, profile)
        run(service)
        _, rules, threshold = fake.calls[0]
        assert [r.label for r in rules] == ["iban"] and threshold == 0.6

    def test_no_enabled_label_never_calls_the_model(self, mocker, fake):
        profile = {"threshold": 0.5, "entities": [entity_rule("x", enabled=False)]}
        out = run(make_service(mocker, fake, profile))
        assert fake.calls == [] and out["pages"][0]["entities"] == []

    def test_on_demand_entities_replace_the_profile(self, service, fake):
        out = run(
            service,
            entities=[
                "siret",
                {"label": "plate", "description": "A car plate", "category": "id"},
            ],
            threshold=0.7,
        )
        _, rules, threshold = fake.calls[0]
        assert [(r.label, r.description) for r in rules] == [
            ("siret", None),
            ("plate", "A car plate"),
        ]
        assert rules[1].category == "ID" and threshold == 0.7
        assert out["profile_version"] is None

    def test_a_profile_description_reaches_the_extractor(self, mocker, fake):
        profile = {
            "threshold": 0.5,
            "entities": [entity_rule("iban", description="A bank account number")],
        }
        run(make_service(mocker, fake, profile))
        assert fake.calls[0][1][0].description == "A bank account number"

    def test_defaults_when_the_backend_is_unreachable(self, mocker, fake):
        def boom():
            raise RuntimeError("down")

        provider = ProfileProvider(
            service_key="k", fallback=NerService._default_profile, fetch=boom
        )
        service = NerService(extractor=fake, profile_provider=provider)
        service.update_task = mocker.Mock()
        run(service)
        assert len(fake.calls[0][1]) == len(DEFAULT_ENTITIES)
        assert fake.calls[0][2] == settings.NER_THRESHOLD

    def test_blank_pages_are_not_sent_to_the_model(self, service, fake):
        out = run(service, " \n ")
        assert fake.calls == []
        assert out["pages"][0]["entities"] == []


class TestInputErrors:
    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            (None, "No page"),
            ({"pages": [{"content": "x"}], "entities": [{"label": ""}]}, "Invalid"),
            ({"pages": [{"content": "x"}], "threshold": 4}, "Invalid"),
            (
                {"pages": [{"content": "x"}], "entities": ["a", "A"]},
                "unique",
            ),
        ],
    )
    def test_bad_input_fails_the_task(self, service, payload, message):
        with pytest.raises(NerError, match=message):
            service.process(payload, task_id="t1")
        assert service.update_task.call_args.kwargs["status"] == "error"

    def test_reports_progress_and_success(self, service):
        run(service)
        statuses = [c.kwargs.get("status") for c in service.update_task.call_args_list]
        assert statuses[0] == "running" and statuses[-1] == "success"


class TestGliner2Extractor:
    RAW = {
        "entities": {
            "email": [{"text": "a@b.c", "confidence": 0.99, "start": 5, "end": 10}],
            "person": [],
        }
    }

    def _extractor(self, mocker, raw=None):
        model = mocker.Mock()
        schema = mocker.MagicMock()
        model.create_schema.return_value.entities.return_value = schema
        model.extract_long.return_value = self.RAW if raw is None else raw
        ext = Gliner2Extractor("m")
        ext._model = model
        return ext, model

    def test_parse_entities(self):
        assert parse_entities(self.RAW) == [RawEntity("email", "a@b.c", 5, 10, 0.99)]

    def test_entities_without_span_are_ignored(self):
        assert parse_entities({"entities": {"x": [{"text": "a"}, "b"]}}) == []
        assert parse_entities({}) == []

    def test_labels_go_as_per_label_config_with_descriptions_and_thresholds(
        self, mocker
    ):
        ext, model = self._extractor(mocker)
        rules = [
            EntityRule(label="email", description="An e-mail address", threshold=0.8),
            EntityRule(label="person"),
        ]
        out = ext.extract("text", rules, 0.5)
        entities = model.create_schema.return_value.entities
        assert entities.call_args.args[0] == {
            "email": {"description": "An e-mail address", "threshold": 0.8},
            "person": {"description": "person"},
        }
        assert entities.call_args.kwargs["threshold"] == 0.5
        assert out == [RawEntity("email", "a@b.c", 5, 10, 0.99)]

    def test_pages_are_read_in_full_with_the_long_context_api(self, mocker):
        ext, model = self._extractor(mocker)
        text = "word " * 5000
        ext.extract(text, [EntityRule(label="email")], 0.5)
        model.extract.assert_not_called()  # no truncating window
        args, kwargs = model.extract_long.call_args
        assert args[0] == text  # the whole page, never cut by the service
        assert kwargs["include_spans"] and kwargs["include_confidence"]
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (384, 64)

    def test_window_size_and_overlap_come_from_the_settings(self, mocker, monkeypatch):
        monkeypatch.setattr(settings, "CHUNK_SIZE", 512)
        monkeypatch.setattr(settings, "CHUNK_OVERLAP", 128)
        ext, model = self._extractor(mocker, {})
        ext.extract("x", [EntityRule(label="a")], 0.5)
        kwargs = model.extract_long.call_args.kwargs
        assert (kwargs["chunk_size"], kwargs["chunk_overlap"]) == (512, 128)

    def test_the_service_sends_a_long_page_in_one_call(self, service, fake):
        text = "Mail a@b.c " + "filler " * 20000
        run(service, text)
        assert [len(t) for t, _, _ in fake.calls] == [len(text)]


class TestBackendsSettingsAndBoxes:
    def test_default_backend(self):
        assert BACKENDS["gliner2"] is Gliner2Extractor
        assert get_extractor().name == f"gliner2:{settings.NER_MODEL}"
        assert settings.NER_MODEL == "fastino/gliner2.5-multi-v1"

    def test_unknown_backend(self):
        with pytest.raises(NerError, match="nope"):
            get_extractor("nope")

    def test_a_new_backend_plugs_in(self, monkeypatch):
        monkeypatch.setitem(BACKENDS, "fake", FakeExtractor)
        monkeypatch.setattr(settings, "NER_BACKEND", "fake")
        svc = NerService.__new__(NerService)
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

    def test_boxes_one_per_line(self):
        def w(x, y, start, end):
            return InputWord(x=x, y=y, width=0.1, height=0.02, start=start, end=end)

        boxes = boxes_for_span(
            [w(0.1, 0.1, 0, 3), w(0.3, 0.1, 4, 7), w(0.1, 0.2, 8, 11)], 0, 11
        )
        assert len(boxes) == 2 and boxes[0].width == pytest.approx(0.3)

    def test_the_default_profile_covers_the_seeded_categories(self):
        by_category: dict[str, set[str]] = {}
        for rule in DEFAULT_ENTITIES:
            by_category.setdefault(rule.category, set()).add(rule.label)
        assert set(by_category) == {"PII", "POLICE", "HEALTH", "LEGAL", "SECRET"}
        assert {"password", "API key"} <= by_category["SECRET"]
        assert len(DEFAULT_ENTITIES) == 32
