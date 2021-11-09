from __future__ import annotations

from contextlib import contextmanager
from logging import Filter, getLogger
from typing import Awaitable, Callable, Iterable, TypeVar, Union

from starlette.responses import Response


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


T = TypeVar('T')


def iter_side_effects(side_effects: Iterable[Union[Callable[..., Awaitable[T]], T]]) -> Callable[..., Awaitable[T]]:
    """
    Args:
        side_effects: An iterable of side effects.

    Returns:
        A side effect that varies from call to call. On the first call, delegating to the first side effect on
         side_effects, on the second to the second, and so on.

    Notes:
        This function respects starlette responses in that if it encounters one, it will simply return it instead of
         delegating to it.
    """
    tor = iter(side_effects)

    async def ret(*args, **kwargs):
        next_side_effect = next(tor)
        if isinstance(next_side_effect, Response):  # responses are async callable smh
            return next_side_effect
        return await next_side_effect(*args, **kwargs)

    return ret
