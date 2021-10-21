from __future__ import annotations

from contextlib import contextmanager
from logging import Filter, getLogger


class MismatchReason(str):
    """
    A falsish object, signifying a failure to match, with a reason.
    """

    @classmethod
    def is_ne(cls, field: str, expected, got) -> MismatchReason:
        """
        Create a mismatch reason that is caused by two values being unequal
        Args:
            field: the name of the mismatched field
            expected: the expected value
            got: the actual value
        """
        return cls(f'{field} mismatch: expected {expected}, got {got}')

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
