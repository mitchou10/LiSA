"""What the documents say never reaches the logs."""

import io
import logging

import pytest
from worker.core.client.base import ClientError
from worker.core.safe_logging import hide_exception_messages, safe_exception_text

SECRET = "Maria Garcia, IBAN FR7630006000011234567890189"


def _raise_chained():
    try:
        raise ValueError(f"cannot parse {SECRET}")
    except ValueError as cause:
        raise RuntimeError(f"failed on\n{SECRET}") from cause


def _exc_info():
    try:
        _raise_chained()
    except RuntimeError as exc:
        return type(exc), exc, exc.__traceback__


def test_the_traceback_keeps_the_frames_and_the_types_but_not_the_messages():
    text = safe_exception_text(_exc_info())
    assert "Maria" not in text and "FR76" not in text
    assert "_raise_chained" in text  # where it happened
    assert "RuntimeError" in text and "ValueError" in text  # what happened
    assert "The above exception was raised while handling another" in text


def test_a_handler_prints_no_exception_message():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("lisa.test.safe")
    logger.propagate = False
    logger.addHandler(handler)
    try:
        hide_exception_messages("lisa.test.safe")
        try:
            _raise_chained()
        except RuntimeError:
            logger.exception("Could not process page %s", 3)
    finally:
        logger.removeHandler(handler)
    out = stream.getvalue()
    assert "Could not process page 3" in out
    assert "RuntimeError" in out
    assert SECRET not in out and "Maria" not in out


def test_an_error_answer_does_not_put_its_detail_in_the_message():
    # A 422 echoes the value that failed validation: the page text.
    detail = [{"type": "string_too_long", "input": SECRET}]
    error = ClientError(422, detail)
    assert str(error) == "HTTP 422"
    assert error.detail == detail  # still there for the code that needs it


def test_celery_lines_do_not_quote_results_or_errors():
    pytest.importorskip("celery")
    from celery.app import trace
    from worker.core.safe_logging import install_celery_safe_logging

    install_celery_safe_logging()
    for line in (
        trace.LOG_SUCCESS,
        trace.LOG_FAILURE,
        trace.LOG_INTERNAL_ERROR,
        trace.LOG_REJECTED,
        trace.LOG_RETRY,
    ):
        assert "return_value" not in line and "%(exc)s" not in line
    # What is left still formats with what Celery gives it.
    assert trace.LOG_SUCCESS % {"name": "ner", "id": "1", "runtime": 0.5} == (
        "Task ner[1] succeeded in 0.5s"
    )


def test_a_failing_celery_task_logs_no_message_and_no_result():
    pytest.importorskip("celery")
    from celery import Celery
    from celery.contrib.testing.worker import start_worker
    from worker.core.safe_logging import install_celery_safe_logging

    install_celery_safe_logging()
    app = Celery("t", broker="memory://", backend="cache+memory://")

    @app.task(name="done")
    def done():
        return {"entities": [SECRET]}

    @app.task(name="boom")
    def boom():
        raise ValueError(f"bad input: {SECRET}")

    # The lines Celery writes about a task come from this logger.
    stream = io.StringIO()
    logger = logging.getLogger("celery.app.trace")
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    hide_exception_messages("celery.app.trace")
    try:
        with start_worker(app, perform_ping_check=False):
            done.delay().get(timeout=10)
            with pytest.raises(ValueError):
                boom.delay().get(timeout=10)
    finally:
        logger.removeHandler(handler)
    logged = stream.getvalue()
    assert "succeeded" in logged and "raised unexpected" in logged
    assert "Maria" not in logged and "FR76" not in logged
