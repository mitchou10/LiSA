"""Keep what the documents say out of the logs.

The pages, the entities found on them and the texts written back can end up in
a log line without anyone logging them on purpose: an exception message that
quotes its input, the body of an error answer, the value a Celery task
returns. Logs are kept and shipped far more widely than the documents are, so
the rule is simple: a log says *what* happened (the exception type, where, the
task id), never *with what*.

``hide_exception_messages`` strips the message of every exception from the
traceback a handler prints. ``install_celery_safe_logging`` does that for a
Celery worker and drops the return value and the exception text from Celery's
own task lines.
"""

from __future__ import annotations

import logging
import traceback
from types import TracebackType
from typing import Any

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def safe_exception_text(exc_info: ExcInfo) -> str:
    """The traceback of ``exc_info`` and of what caused it, without any message.

    Frames (file, line, code) and the exception types are kept: that is what is
    needed to debug. The messages are dropped, they quote the data.
    """
    chain: list[BaseException] = []
    exc: BaseException | None = exc_info[1]
    while exc is not None and all(exc is not seen for seen in chain):
        chain.append(exc)
        exc = exc.__cause__ or exc.__context__
    blocks = []
    for item in reversed(chain):
        frames = "".join(
            traceback.format_list(traceback.extract_tb(item.__traceback__))
        )
        kind = f"{type(item).__module__}.{type(item).__qualname__}"
        blocks.append(f"Traceback (most recent call last):\n{frames}{kind}")
    return "\n\nThe above exception was raised while handling another:\n\n".join(blocks)


def hide_exception_messages(*logger_names: str) -> None:
    """Print tracebacks without exception messages on these loggers' handlers.

    No name: the root logger. Call it once the handlers are in place.
    """
    for name in logger_names or ("",):
        for handler in logging.getLogger(name).handlers:
            formatter = handler.formatter or logging.Formatter()
            formatter.formatException = lambda ei: safe_exception_text(ei)  # type: ignore[method-assign]
            handler.setFormatter(formatter)


# Celery's own task lines, minus what they quote: the value a task returned
# and the text of the exception it raised.
_CELERY_LINES: dict[str, str] = {
    "LOG_SUCCESS": "Task %(name)s[%(id)s] succeeded in %(runtime)ss",
    "LOG_FAILURE": "Task %(name)s[%(id)s] %(description)s",
    "LOG_INTERNAL_ERROR": "Task %(name)s[%(id)s] %(description)s",
    "LOG_REJECTED": "Task %(name)s[%(id)s] rejected",
    "LOG_RETRY": "Task %(name)s[%(id)s] retry",
}

# Where Celery's workers log: the root logger and the task logger.
_CELERY_LOGGERS = ("", "celery", "celery.task")


def install_celery_safe_logging() -> None:
    """Make a Celery worker log without the data it processes."""
    from celery import signals
    from celery.app import trace

    old = {getattr(trace, attribute): line for attribute, line in _CELERY_LINES.items()}
    for attribute, line in _CELERY_LINES.items():
        setattr(trace, attribute, line)
    # The failure lines are read from policies built when Celery was imported.
    for name in dir(trace):
        policy = getattr(trace, name)
        if name.startswith("log_policy_") and isinstance(policy, tuple):
            setattr(
                trace,
                name,
                policy._replace(format=old.get(policy.format, policy.format)),
            )

    def _hide(*_args: Any, **_kwargs: Any) -> None:
        hide_exception_messages(*_CELERY_LOGGERS)

    # Celery builds its handlers when the worker starts: do it again then.
    for signal in (signals.after_setup_logger, signals.after_setup_task_logger):
        signal.connect(_hide, weak=False)
    _hide()
