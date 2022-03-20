from __future__ import annotations

from contextlib import contextmanager
from typing import (
    TYPE_CHECKING, Awaitable, Callable, ContextManager, Iterable, Iterator, List, Optional, Tuple, Union, overload
)

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import BaseRoute, Route
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, WS_1011_INTERNAL_ERROR
from starlette.websockets import WebSocket

from yellowbox.extras.webserver.http_request_capture import RecordedHTTPRequest, RecordedHTTPRequests
from yellowbox.extras.webserver.ws_request_capture import RecordedWSTranscripts, RecorderEndpoint

BASE_HTTP_SIDE_EFFECT = Union[Response, Callable[[Request], Awaitable[Response]]]
BASE_WS_SIDE_EFFECT = Callable[[WebSocket], Awaitable[Optional[int]]]

HTTP_SIDE_EFFECT = Union[BASE_HTTP_SIDE_EFFECT, Callable[['MockHTTPEndpoint'], BASE_HTTP_SIDE_EFFECT]]
WS_SIDE_EFFECT = Union[BASE_WS_SIDE_EFFECT, Callable[['MockWSEndpoint'], BASE_WS_SIDE_EFFECT]]
METHODS = Union[str, Iterable[str]]

if TYPE_CHECKING:
    from yellowbox.extras.webserver.webserver import WebServer


class EndpointPatch(ContextManager):
    """
    A the return value of endpoint side effect patches, restores the original side effect if ever exited
    """

    def __init__(self, endpoint: Union[MockHTTPEndpoint, MockWSEndpoint], restore_side_effect):
        self.endpoint = endpoint
        self.restore_side_effect = restore_side_effect

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.endpoint.side_effect = self.restore_side_effect
        self.endpoint.owner._raise_from_pending()


@overload
def bind_side_effect(endpoint: MockHTTPEndpoint, side_effect: HTTP_SIDE_EFFECT) -> BASE_HTTP_SIDE_EFFECT:
    pass


@overload
def bind_side_effect(endpoint: MockWSEndpoint, side_effect: WS_SIDE_EFFECT) -> BASE_WS_SIDE_EFFECT:
    pass


def bind_side_effect(endpoint, side_effect):
    if callable(side_effect) and getattr(side_effect, '__side_effect_factory__', False):
        return side_effect(endpoint)
    return side_effect


class MockHTTPEndpoint:
    """
    A mock http endpoint for a webserver
    """

    def __init__(self, name: str, methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT,
                 auto_read_body: bool = True, forbid_implicit_head_verb: bool = True):
        """
        Args:
            name: the name of the endpoint
            methods: the methods by which the endpoint is accessible
            rule_string: the rule-string of the endpoint, as specified by starlette routes
            side_effect: the side effect of the endpoint. This can be either a starlette response, or an async callable
             that accepts a starlette request and returns a starlette response.
            auto_read_body: If true (the default), the request is always awaited to be received in full before replying
             to the client.
            forbid_implicit_head_verb: By default, starlette automatically makes all routes that are accessible by the
             GET method also accessible through the HEAD method. If this parameter is set to true (the default),
             this behaviour is disabled and HEAD must be added explicitly if required.
        """
        self._request_captures: List[RecordedHTTPRequests] = []
        self.owner: Optional[WebServer] = None

        if isinstance(methods, str):
            methods = (methods,)

        self.methods: Tuple[str, ...] = tuple(m.upper() for m in methods)
        self.rule_string = rule_string
        self.__name__ = name
        self.auto_read_body = auto_read_body
        self.forbid_implicit_head_verb = forbid_implicit_head_verb

        self.side_effect = bind_side_effect(self, side_effect)

    def patch(self, side_effect: HTTP_SIDE_EFFECT):
        """
        Change the side effect of the endpoint
        Args:
            side_effect: the new side effect of the endpoint

        Returns:
            A context manager that, if exited, restores the endpoint's original side effect
        """
        self.owner._raise_from_pending()
        previous_side_effect = self.side_effect
        self.side_effect = bind_side_effect(self, side_effect)
        return EndpointPatch(self, previous_side_effect)

    @contextmanager
    def capture_calls(self) -> Iterator[RecordedHTTPRequests]:
        """
        A context manager that records all requests to the endpoint in its scope to a list
        Returns:
             A RecordedHTTPRequests to which the requests are recorded
        """
        self.owner._raise_from_pending()
        if not self.auto_read_body:
            raise RuntimeError("cannot capture calls if auto_read_body is disabled")
        calls = RecordedHTTPRequests()
        self._request_captures.append(calls)
        try:
            yield calls
        finally:
            if self._request_captures[-1] is not calls:
                raise RuntimeError('capture_calls contexts cannot be used in parallel')
            self._request_captures.pop()
            self.owner._raise_from_pending()

    async def get(self, request: Request):
        # the target of the starlette route
        if not self.owner:
            raise RuntimeError('endpoint must be assigned to a webserver')
        if self.owner._pending_exception:
            return PlainTextResponse(
                f'an exception in the webserver had previously occurred: {self.owner._pending_exception!r}',
                status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )
        try:
            if isinstance(self.side_effect, Response):
                ret = self.side_effect
            else:
                ret = await self.side_effect(request)
        except Exception as ex:
            self.owner._pending_exception = ex
            return PlainTextResponse(f'handler raised an exception: {ex!r}', status_code=HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            if self.auto_read_body:
                await request.body()
            if self._request_captures:  # recording the request reads its body, which we might not want
                recorded = await RecordedHTTPRequest.from_request(request)
                for c in self._request_captures:
                    c.append(recorded)
        return ret

    def route(self) -> BaseRoute:
        """
        Returns: a starlette route representing the endpoint
        """
        ret = Route(self.rule_string, self.get, methods=self.methods, name=self.__name__)  # type:ignore[arg-type]
        if self.forbid_implicit_head_verb and 'HEAD' not in self.methods:
            ret.methods.discard('HEAD')
        return ret


@overload
def http_endpoint(methods: METHODS, rule_string: str, *, auto_read_body: bool = True, forbid_head_verb: bool = True,
                  name: str = None) \
        -> Callable[[HTTP_SIDE_EFFECT], MockHTTPEndpoint]: ...


@overload
def http_endpoint(methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *, auto_read_body: bool = True,
                  forbid_implicit_head_verb: bool = True, name: str = None) -> MockHTTPEndpoint: ...


def http_endpoint(methods: METHODS, rule_string: str, side_effect: Optional[HTTP_SIDE_EFFECT] = None, *,
                  name: Optional[str] = None, **kwargs):
    """
    Create a mock HTTP endpoint.
    Args:
        methods: forwarded to MockHTTPEndpoint
        rule_string: forwarded to MockHTTPEndpoint
        side_effect: forwarded to MockHTTPEndpoint
        name: forwarded to MockHTTPEndpoint, if none, an automaitic name is generated.
        **kwargs: forwarded to MockHTTPEndpoint

    Returns:
        an http endpoint

    Notes:
        can also be used as a decorator, when decorating the side effect

    Examples:
        >>> @http_endpoint('GET', '/bar')
        ... async def bar(request: Request):
        ...   return PlainTextResponse(int(request.query_params['x'])**2)
        ...
        ... WebServer().add_http_endpoint(bar)

    """

    def ret(func: HTTP_SIDE_EFFECT):
        nonlocal name
        if name is None and not getattr(func, '__skip_name_for_side_effect__', False):
            try:
                name = func.__name__  # type: ignore[union-attr]
            except AttributeError:
                pass
        if name is None:
            name = f'{methods} {rule_string}'
        return MockHTTPEndpoint(name, methods, rule_string, func, **kwargs)

    if side_effect is None:
        return ret
    return ret(side_effect)


class MockWSEndpoint:
    """
    A mock websocket endpoint for a webserver
    """

    def __init__(self, name: str, rule_string: str, side_effect: WS_SIDE_EFFECT):
        """
        Args:
            name: the name of the endpoint
            rule_string: the rule-string of the endpoint, as specified by starlette routes
            side_effect: the side effect of the endpoint. This should be an async callable that accepts a starlette
             websocket and optionally returns an int to close the connection with that code.
        """
        self._request_captures: List[RecordedWSTranscripts] = []
        self.owner: Optional[WebServer] = None

        self.rule_string = rule_string
        self.__name__ = name
        self.side_effect = bind_side_effect(self, side_effect)

        # this will be the endpoint handed to the starlette.WebSocketRoute. By storing it as an
        # attribute of the endpoint, we will be able to better locate routes relating to the endpoint
        self.endpoint = RecorderEndpoint(function=self.get, sinks=self._request_captures)

    async def get(self, websocket: WebSocket):
        # this will be the function that our endpoint will eventually route to
        if not self.owner:
            await websocket.close(WS_1011_INTERNAL_ERROR)  # note that this will actually send a 403 code :shrug:
            return
        if self.owner._pending_exception:
            await websocket.close(WS_1011_INTERNAL_ERROR)  # note that this will actually send a 403 code :shrug:
            return
        try:
            code = await self.side_effect(websocket)
        except Exception as ex:
            self.owner._pending_exception = ex
            await websocket.close(WS_1011_INTERNAL_ERROR)
        else:
            if code is not None:
                await websocket.close(code)

    def patch(self, side_effect: WS_SIDE_EFFECT):
        """
        Change the side effect of the endpoint
        Args:
            side_effect: the new side effect of the endpoint

        Returns:
            A context manager that, if exited, restores the endpoint's original side effect
        """
        self.owner._raise_from_pending()
        previous_side_effect = self.side_effect
        self.side_effect = bind_side_effect(self, side_effect)
        return EndpointPatch(self, previous_side_effect)

    @contextmanager
    def capture_calls(self) -> Iterator[RecordedWSTranscripts]:
        self.owner._raise_from_pending()
        calls = RecordedWSTranscripts()
        self._request_captures.append(calls)
        try:
            yield calls
        finally:
            if self._request_captures[-1] is not calls:
                raise RuntimeError('capture_calls contexts cannot be used in parallel')
            self._request_captures.pop()
            self.owner._raise_from_pending()


@overload
def ws_endpoint(rule_string: str, *, name: str = None) -> Callable[[WS_SIDE_EFFECT], MockWSEndpoint]: pass


@overload
def ws_endpoint(rule_string: str, side_effect: WS_SIDE_EFFECT, *, name: str = None) -> MockWSEndpoint: pass


def ws_endpoint(rule_string: str, side_effect: Optional[WS_SIDE_EFFECT] = None, *, name: str = None):
    """
    Create a mock websocket endpoint.
    Args:
        rule_string: forwarded to MockWSEndpoint
        side_effect: forwarded to MockWSEndpoint
        name: forwarded to MockWSEndpoint. If not specified, a name will be the generated.

    Returns:
        a websocket endpoint

    Notes:
        can also be used as a decorator, when decorating the side effect

    Examples:
        >>> @ws_endpoint('/square')
        ... async def square(ws: WebSocket):
        ...   await ws.accept()
        ...   x = int(await ws.receive_text())
        ...   await ws.send_text(str(x*x))
        ...   await ws.close()
        ...
        ... WebServer().add_ws_endpoint(square)
    """

    def ret(func: WS_SIDE_EFFECT):
        nonlocal name
        if name is None and not getattr(func, '__skip_name_for_side_effect__', False):
            try:
                name = func.__name__
            except AttributeError:
                pass
        if name is None:
            name = rule_string
        return MockWSEndpoint(name, rule_string, func)

    if side_effect is None:
        return ret
    return ret(side_effect)
