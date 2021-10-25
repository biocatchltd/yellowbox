from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from threading import Lock, Thread
from time import sleep
from typing import Awaitable, Callable, ContextManager, Iterable, Iterator, List, Optional, Tuple, Union, overload

from requests import ConnectionError, HTTPError, get
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import BaseRoute, Route, WebSocketRoute
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, WS_1011_INTERNAL_ERROR
from starlette.websockets import WebSocket
from uvicorn import Config, Server
from uvicorn.config import LOGGING_CONFIG

from yellowbox import YellowService
from yellowbox.extras.webserver.http_request_capture import RecordedHTTPRequest, RecordedHTTPRequests
from yellowbox.extras.webserver.util import mute_uvicorn_log
from yellowbox.extras.webserver.ws_request_capture import RecordedWSTranscripts, recorder_websocket_endpoint
from yellowbox.retry import RetrySpec
from yellowbox.utils import docker_host_name


class HandlerError(Exception):
    """
    An exception occurred while handling an endpoint in the webserver thread
    """


HTTP_SIDE_EFFECT = Union[Response, Callable[[Request], Awaitable[Response]]]
WS_SIDE_EFFECT = Callable[[WebSocket], Awaitable[Optional[int]]]
METHODS = Union[str, Iterable[str]]


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
        self.side_effect = side_effect
        self.auto_read_body = auto_read_body
        self.forbid_implicit_head_verb = forbid_implicit_head_verb

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
        self.side_effect = side_effect
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
def http_endpoint(methods: METHODS, rule_string: str, *, auto_read_body: bool = True, forbid_head_verb: bool = True) \
        -> Callable[[HTTP_SIDE_EFFECT], MockHTTPEndpoint]: ...


@overload
def http_endpoint(methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *, auto_read_body: bool = True,
                  forbid_implicit_head_verb: bool = True) -> MockHTTPEndpoint: ...


def http_endpoint(methods: METHODS, rule_string: str, side_effect: Optional[HTTP_SIDE_EFFECT] = None, **kwargs):
    """
    Create a mock HTTP endpoint.
    Args:
        methods: forwarded to MockHTTPEndpoint
        rule_string: forwarded to MockHTTPEndpoint
        side_effect: forwarded to MockHTTPEndpoint
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
        try:
            name = func.__name__  # type: ignore[union-attr]
        except AttributeError:
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
        self.side_effect = side_effect

        # this will be the endpoint handed to the starlette.WebSocketRoute.
        # the route chooses whether to hand off the scope, receive, send functions (which we need) only if we fail
        # inspect.isfunction and inspect.ismethod. Fortunately, partial fails these tests. By storing it as an
        # attribute of the endpoint, we will be able to better locate routes relating to the endpoint
        self.endpoint = partial(recorder_websocket_endpoint, function=self.get, sinks=self._request_captures)

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
        self.side_effect = side_effect
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
def ws_endpoint(rule_string: str) -> Callable[[WS_SIDE_EFFECT], MockWSEndpoint]: pass


@overload
def ws_endpoint(rule_string: str, side_effect: WS_SIDE_EFFECT) -> MockWSEndpoint: pass


def ws_endpoint(rule_string: str, side_effect: Optional[WS_SIDE_EFFECT] = None):
    """
    Create a mock websocket endpoint.
    Args:
        rule_string: forwarded to MockWSEndpoint
        side_effect: forwarded to MockWSEndpoint

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
        return MockWSEndpoint(func.__name__, rule_string, func)

    if side_effect is None:
        return ret
    return ret(side_effect)


DEFAULT_LOG_CONFIG = deepcopy(LOGGING_CONFIG)


class WebServer(YellowService):
    """
    An easy-to-modify HTTP and websocket server, wrapping a starlette application
    """
    PORT_ACCESS_MAX_RETRIES = 100  # the maximum number of attempts to make when accessing a binding port. Each attempt
    # has an interval of 0.01 seconds

    def __init__(self, name: str, port: Optional[int] = None, log_config=DEFAULT_LOG_CONFIG, **kwargs):
        """
        Args:
            name: the name of the service
            port: the port to bind to when serving, default will bind to an available port
            log_config: the logging configuration fot the uvicorn server. On default, will override the access format
             to include the service name.
            **kwargs: forwarded to the uvicorn configuration.
        """
        self._app = Starlette(debug=True)
        self._route_lock = Lock()

        # since the main thread won't catch errors in handlers, this class will store any error raised while handling,
        #  and raise them in the main thread as soon as we can
        self._pending_exception: Optional[Exception] = None

        if log_config is DEFAULT_LOG_CONFIG:
            log_config = deepcopy(DEFAULT_LOG_CONFIG)
            log_config['formatters']['access']['fmt'] = f'%(levelprefix)s {name} - "%(request_line)s" %(status_code)s'

        self._port = port

        config = Config(self._app, **kwargs, port=self._port, log_config=log_config)
        self._server = Server(config)
        self._serve_thread = Thread(name=f'{name}_thread', target=self._server.run)

    @property
    def port(self) -> Optional[int]:
        """
        Returns:
            The port the service is bound to, if the service is binding to anything.

        Notes:
            Will only return None if the port was not provided during construction and the service thread is not running
            If the service is starting up, this property will block until the port is binded, or raise an error if
            blocked for longer than 1 second.
        """
        if self._port or not self._serve_thread.is_alive():
            return self._port
        for _ in range(self.PORT_ACCESS_MAX_RETRIES):
            servers = getattr(self._server, 'servers', None)
            if servers:
                sockets = getattr(servers[0], 'sockets', None)
                if sockets:
                    socket = sockets[0]
                    break
            sleep(0.01)
        else:
            raise RuntimeError('timed out when getting binding port')
        self._port = socket.getsockname()[1]
        return self._port

    @overload
    def add_http_endpoint(self, endpoint: MockHTTPEndpoint) -> MockHTTPEndpoint:
        ...

    @overload
    def add_http_endpoint(self, methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *,
                          auto_read_body: bool = True, forbid_implicit_head_verb: bool = True) -> MockHTTPEndpoint:
        ...

    def add_http_endpoint(self, *args, **kwargs) -> MockHTTPEndpoint:
        """
        Add an http endpoint to the server
        Args:
            *args: either a single mock http endpoint, or parameters forwarded to http_endpoint construct one
            **kwargs: forwarded to http_endpoint to construct an endpoint

        Returns:
            the http endpoint added to the server
        """
        self._raise_from_pending()
        if len(args) == 1 and not kwargs:
            ep, = args
        else:
            ep = http_endpoint(*args, **kwargs)
        if ep.owner is not None:
            raise RuntimeError('an endpoint cannot be added twice')
        with self._route_lock:
            self._app.routes.append(
                ep.route()
            )
        ep.owner = self
        return ep

    def remove_http_endpoint(self, endpoint: MockHTTPEndpoint):
        """
        Remove an http endpoint previously added to the server
        Args:
            endpoint: the endpoint to remove
        """
        self._raise_from_pending()
        if endpoint.owner is not self:
            raise RuntimeError('endpoint is not added to the server')
        with self._route_lock:
            for i, route in enumerate(self._app.router.routes):
                if isinstance(route, Route) and route.endpoint == endpoint.get:
                    break
            else:
                raise RuntimeError('endpoint is not found in the server')
            self._app.router.routes.pop(i)
            endpoint.owner = None

    @overload
    def patch_http_endpoint(self, endpoint: MockHTTPEndpoint) -> ContextManager[MockHTTPEndpoint]:
        ...

    @overload
    def patch_http_endpoint(self, methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *,
                            auto_read_body: bool = True, forbid_head_verb: bool = True) \
            -> ContextManager[MockHTTPEndpoint]:
        ...

    @contextmanager  # type:ignore[misc]
    def patch_http_endpoint(self, *args, **kwargs) -> Iterator[MockHTTPEndpoint]:
        """
        A context manager to add and then remove an http endpoint
        Args:
            *args: forwarded to self.add_http_endpoint
            **kwargs: forwarded to self.add_http_endpoint

        Returns:
            The temporarily added endpoint
        """
        ep = self.add_http_endpoint(*args, **kwargs)
        try:
            yield ep
        finally:
            self.remove_http_endpoint(ep)

    @overload
    def add_ws_endpoint(self, endpoint: MockWSEndpoint) -> MockWSEndpoint:
        ...

    @overload
    def add_ws_endpoint(self, rule_string: str, side_effect: WS_SIDE_EFFECT) -> MockWSEndpoint:
        ...

    def add_ws_endpoint(self, *args, **kwargs):
        """
        Add a websocket endpoint to the server
        Args:
            *args: either a single mock ws endpoint, or parameters forwarded to ws_endpoint construct one
            **kwargs: forwarded to ws_endpoint to construct an endpoint

        Returns:
            the websocket endpoint added to the server
        """
        self._raise_from_pending()
        if len(args) == 1 and not kwargs:
            ep, = args
        else:
            ep = ws_endpoint(*args, **kwargs)

        if ep.owner is not None:
            raise RuntimeError('an endpoint cannot be added twice')

        with self._route_lock:
            self._app.routes.append(
                WebSocketRoute(ep.rule_string, ep.endpoint, name=ep.__name__)
            )
        ep.owner = self
        return ep

    def remove_ws_endpoint(self, endpoint: MockWSEndpoint):
        """
        Remove a websocket endpoint previously added to the server
        Args:
            endpoint: the endpoint to remove
        """
        self._raise_from_pending()
        if endpoint.owner is not self:
            raise RuntimeError('endpoint is not added to the server')
        with self._route_lock:
            for i, route in enumerate(self._app.router.routes):
                if isinstance(route, WebSocketRoute) and route.app == endpoint.endpoint:
                    break
            else:
                raise RuntimeError('endpoint is not found in the server')
            self._app.router.routes.pop(i)
            endpoint.owner = None

    @overload
    def patch_ws_endpoint(self, endpoint: MockWSEndpoint) -> ContextManager[MockWSEndpoint]:
        ...

    @overload
    def patch_ws_endpoint(self, rule_string: str, side_effect: WS_SIDE_EFFECT) -> ContextManager[MockWSEndpoint]:
        ...

    @contextmanager  # type:ignore[misc]
    def patch_ws_endpoint(self, *args, **kwargs):
        """
        A context manager to add and then remove a ws endpoint
        Args:
            *args: forwarded to self.add_ws_endpoint
            **kwargs: forwarded to self.add_ws_endpoint

        Returns:
            The temporarily added endpoint
        """
        ep = self.add_ws_endpoint(*args, **kwargs)
        try:
            yield ep
        finally:
            self.remove_ws_endpoint(ep)

    def local_url(self, schema: Optional[str] = 'http') -> str:
        """
        Get the url to access this server from the local machine
        Args:
            schema: the optional schema of the url, defaults to http
        """
        if schema is None:
            return f'localhost:{self.port}'
        return f'{schema}://localhost:{self.port}'

    def container_url(self, schema='http') -> str:
        """
        Get the url to access this server from a docker container running in the local machine
        Args:
            schema: the optional schema of the url, defaults to http
        """
        if schema is None:
            return f'{docker_host_name}:{self.port}'
        return f'{schema}://{docker_host_name}:{self.port}'

    def start(self, retry_spec: Optional[RetrySpec] = None) -> WebServer:
        if self._serve_thread.is_alive():
            raise RuntimeError('thread cannot be started twice')
        with mute_uvicorn_log():
            self._serve_thread.start()
            with self.patch_http_endpoint('GET', '/__yellowbox/ping', side_effect=PlainTextResponse('')):
                retry_spec = retry_spec or RetrySpec(interval=0.1, timeout=5)
                retry_spec.retry(
                    lambda: get(self.local_url() + '/__yellowbox/ping').raise_for_status(),
                    (ConnectionError, HTTPError)
                )
        return super().start()

    def stop(self):
        with mute_uvicorn_log():
            self._server.should_exit = True
            self._serve_thread.join()
        super().stop()
        self._raise_from_pending()

    def is_alive(self) -> bool:
        self._raise_from_pending()
        return self._serve_thread.is_alive()

    def _raise_from_pending(self):
        # if there is a pending exception, this will raise it
        if self._pending_exception:
            pending = self._pending_exception
            self._pending_exception = None
            raise HandlerError() from pending
