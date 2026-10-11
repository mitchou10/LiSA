"""Tests for the live detection profile provider."""

from __future__ import annotations

import json
import time

from app.profile import ProfileProvider

DEFAULT = {"version": None, "threshold": 0.5, "entities": [{"label": "default"}]}


def _config(*entities, threshold=0.5):
    return {"threshold": threshold, "entities": list(entities)}


def _entity(label, category="PII", **kw):
    return {
        "label": label,
        "category": category,
        "severity": "medium",
        "action": "redact",
        "enabled": True,
        "threshold": None,
        **kw,
    }


class TestProfileProvider:
    def test_static_provider_uses_fallback(self):
        provider = ProfileProvider(service_key="k", fallback=lambda: DEFAULT)
        assert provider.get() is DEFAULT

    def test_fetches_lazily_and_caches(self):
        calls = []

        def fetch():
            calls.append(1)
            return 3, _config(_entity("iban"))

        provider = ProfileProvider(
            service_key="k", fallback=lambda: DEFAULT, fetch=fetch
        )
        assert provider.get()["version"] == 3
        provider.get()
        assert len(calls) == 1

    def test_falls_back_when_backend_down(self):
        def fetch():
            raise ConnectionError("down")

        provider = ProfileProvider(
            service_key="k", fallback=lambda: DEFAULT, fetch=fetch
        )
        assert provider.get() is DEFAULT

    def test_keeps_last_profile_when_refresh_fails(self):
        state = {"ok": True}

        def fetch():
            if state["ok"]:
                return 1, _config(_entity("iban"))
            raise ConnectionError("down")

        provider = ProfileProvider(
            service_key="k", fallback=lambda: DEFAULT, fetch=fetch
        )
        assert provider.get()["version"] == 1
        state["ok"] = False
        assert provider.refresh() is False
        assert provider.get()["version"] == 1

    def test_refresh_swaps_profile(self):
        versions = iter([1, 2])
        provider = ProfileProvider(
            service_key="k",
            fallback=lambda: DEFAULT,
            fetch=lambda: (next(versions), _config(_entity("iban"))),
        )
        assert provider.get()["version"] == 1
        provider.refresh()
        assert provider.get()["version"] == 2

    def test_matches_only_own_service_key(self):
        provider = ProfileProvider(service_key="gliner-ner", fallback=lambda: DEFAULT)
        assert provider._matches(
            json.dumps({"service_key": "gliner-ner", "version": 2})
        )
        assert not provider._matches(json.dumps({"service_key": "other"}))
        assert not provider._matches("not json")
        assert not provider._matches(None)

    def test_push_message_triggers_refresh(self, monkeypatch):
        """A pub/sub message for our key makes the listener re-fetch."""
        import app.profile as profile_module

        queue: list[dict] = []

        class FakePubSub:
            def subscribe(self, _channel):
                pass

            def get_message(self, timeout=None):
                time.sleep(0.01)
                return queue.pop(0) if queue else None

        class FakeRedis:
            @classmethod
            def from_url(cls, _url):
                return cls()

            def pubsub(self, **_kw):
                return FakePubSub()

        monkeypatch.setattr("redis.Redis", FakeRedis)
        current = {"version": 1}
        provider = ProfileProvider(
            service_key="k",
            fallback=lambda: DEFAULT,
            fetch=lambda: (current["version"], _config(_entity("iban"))),
            redis_url="redis://fake",
            refresh_seconds=3600,
        )
        assert provider.get()["version"] == 1

        current["version"] = 2
        queue.append({"data": json.dumps({"service_key": "other", "version": 9})})
        queue.append({"data": json.dumps({"service_key": "k", "version": 2})})
        deadline = time.time() + 3
        while time.time() < deadline and provider.get()["version"] != 2:
            time.sleep(0.02)
        assert provider.get()["version"] == 2
        assert profile_module  # module imported without side effects
