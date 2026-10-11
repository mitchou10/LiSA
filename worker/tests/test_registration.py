"""Registration waits for the backend instead of giving up at the first refusal."""

import httpx
import pytest
from worker.core.client.base import ClientError
from worker.core.services.base import BaseService


class FakeClient:
    """Fails with the given errors in order, then answers."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.created = []

    def find_by_name(self, name):
        if self.errors:
            raise self.errors.pop(0)

    def create(self, definition):
        self.created.append(definition)
        return {"id": "svc-1", **definition}


class Demo(BaseService):
    name = "demo"

    def process(self, input_data, task_id=None):
        return {}


def service(errors):
    svc = Demo.__new__(Demo)  # no HTTP clients: the fake stands in
    svc._client = FakeClient(errors)
    svc.id = None
    return svc


refused = httpx.ConnectError("Connection refused")


def test_registers_at_once_when_the_backend_is_up():
    svc = service([])
    sleeps = []
    assert svc.register_with_retry(sleep=sleeps.append)["id"] == "svc-1"
    assert sleeps == [] and svc.id == "svc-1"


def test_waits_for_the_backend_then_registers():
    svc = service([refused, refused, ClientError(503, "starting")])
    sleeps = []
    result = svc.register_with_retry(delay=2, sleep=sleeps.append)
    assert result["id"] == "svc-1"
    assert len(sleeps) == 3 and sleeps[0] == 2 and sleeps[1] > sleeps[0]


def test_the_delay_stops_growing():
    svc = service([refused] * 8)
    sleeps = []
    svc.register_with_retry(delay=2, max_delay=5, sleep=sleeps.append)
    assert max(sleeps) == 5


def test_gives_up_after_the_attempts():
    svc = service([refused] * 10)
    sleeps = []
    assert svc.register_with_retry(attempts=3, sleep=sleeps.append) is None
    assert len(sleeps) == 2  # no wait after the last attempt
    assert svc._client.created == []


@pytest.mark.parametrize("status", [401, 403, 422])
def test_a_client_error_is_not_retried(status):
    svc = service([ClientError(status, "nope")])
    sleeps = []
    assert svc.register_with_retry(sleep=sleeps.append) is None
    assert sleeps == []


def test_background_registration_does_not_block():
    svc = service([refused])
    thread = svc.register_in_background(delay=0, sleep=lambda _: None)
    thread.join(timeout=5)
    assert not thread.is_alive() and svc.id == "svc-1"
