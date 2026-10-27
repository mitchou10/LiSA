"""What the documents say never reaches the backend's logs."""

import io
import logging

from app.core.safe_logging import hide_exception_messages, safe_exception_text

SECRET = "Maria Garcia, IBAN FR7630006000011234567890189"


def _raise():
    raise ValueError(f"1 validation error for Output\n  input_value={SECRET!r}")


def test_a_traceback_has_no_exception_message():
    try:
        _raise()
    except ValueError as exc:
        text = safe_exception_text((type(exc), exc, exc.__traceback__))
    assert "Maria" not in text and "FR76" not in text
    assert "_raise" in text and "ValueError" in text


def test_a_handler_prints_no_exception_message():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("lisa.test.backend.safe")
    logger.propagate = False
    logger.addHandler(handler)
    try:
        hide_exception_messages("lisa.test.backend.safe")
        try:
            _raise()
        except ValueError:
            logger.exception("Unhandled error")
    finally:
        logger.removeHandler(handler)
    out = stream.getvalue()
    assert "Unhandled error" in out and "ValueError" in out
    assert SECRET not in out
