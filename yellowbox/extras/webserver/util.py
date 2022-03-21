from __future__ import annotations

import sys
from datetime import datetime
from functools import update_wrapper
from logging import Filter
from typing import TYPE_CHECKING, Awaitable, Callable, Iterable, TypeVar, Union

from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from yellowbox.extras.webserver.endpoints import BASE_HTTP_SIDE_EFFECT, HTTP_SIDE_EFFECT, MockHTTPEndpoint


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

    # we don't want the inner function's __name__ to be the endpoint's name
    ret.__skip_name_for_side_effect__ = True  # type: ignore[attr-defined]

    return ret


def _DEFAULT_MESSAGE_FACTORY(endpoint: MockHTTPEndpoint, request: Request, response: Response) -> str:
    client = f'{request.client.host}:{request.client.port}'
    relative_path = request.url.path
    if request.url.query:
        relative_path += f'?{request.url.query}'
    return f'{datetime.now().isoformat(sep=" ", timespec="seconds")} {endpoint.owner.__name__}:{endpoint.__name__} ' \
           f'{client} - {request.method} {relative_path} {response.status_code} ({len(response.body)} bytes)'


def verbose_http_side_effect(side_effect: BASE_HTTP_SIDE_EFFECT,
                             format_function: Callable[[MockHTTPEndpoint, Request, Response], str]
                             = _DEFAULT_MESSAGE_FACTORY,
                             file=sys.stdout) -> HTTP_SIDE_EFFECT:
    """
    Wrap a side effect so that it prints the arguments and return value on each call.
    """

    def side_effect_factory(endpoint: MockHTTPEndpoint):
        async def side_effect_wrapper(request: Request):
            if isinstance(side_effect, Response):
                response = side_effect
            else:
                response = await side_effect(request)

            message = format_function(endpoint, request, response)
            print(message, file=file)
            return response

        if not isinstance(side_effect, Response):
            update_wrapper(side_effect_wrapper, side_effect)
        else:
            # we don't want the inner function's __name__ to be the endpoint's name
            side_effect_wrapper.__skip_name_for_side_effect__ = True  # type: ignore[attr-defined]
        return side_effect_wrapper

    side_effect_factory.__side_effect_factory__ = True  # type: ignore[attr-defined]
    return side_effect_factory
