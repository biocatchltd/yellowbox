from __future__ import annotations

from contextlib import contextmanager
from logging import Filter, getLogger


def reason_is_ne(field: str, expected, got) -> str:
    """
    Create a string that is describes two values being unequal
    Args:
        field: the name of the mismatched field
        expected: the expected value
        got: the actual value
    """
    return f'{field} mismatch: expected {expected}, got {got}'


class MismatchReason(str):
    """
    A falsish object, signifying a failure to match, with a reason.
    """

    def __bool__(self):
        return False


class MuteFilter(Filter):
    """
    A simple filter that silences all logs
    """

    def filter(self, record) -> bool:
        return False


@contextmanager
def mute_uvicorn_log():
    """
    A context manager to silence all log messages from the uvicorn.error logger while in its scope
    """
    logger = getLogger('uvicorn.error')
    filter_ = MuteFilter()
    logger.addFilter(filter_)
    yield
    logger.removeFilter(filter_)
