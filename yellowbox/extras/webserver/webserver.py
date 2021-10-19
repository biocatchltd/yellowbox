from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from threading import Lock, Thread
from traceback import print_exc
from typing import List, Union, Iterable, Optional, Callable, Tuple, Awaitable, ContextManager, overload

from requests import get, HTTPError, ConnectionError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route, WebSocketRoute, BaseRoute
from starlette.websockets import WebSocket
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, WS_1011_INTERNAL_ERROR
from uvicorn import Server, Config
from uvicorn.config import LOGGING_CONFIG

from yellowbox import YellowService
from yellowbox.extras.webserver.http_request_capture import RecordedHTTPRequests, RecordedHTTPRequest
from yellowbox.extras.webserver.util import mute_uvicorn_log
from yellowbox.extras.webserver.ws_request_capture import RecordedWSTranscripts, recorder_websocket_endpoint
from yellowbox.retry import RetrySpec
from yellowbox.utils import docker_host_name, get_free_port


class HandlerError(Exception):
    """
    An exception occurred while handling an endpoint in the webserver thread
    """


HTTP_SIDE_EFFECT = Union[Response, Callable[[Request], Awaitable[Response]]]
WS_SIDE_EFFECT = Callable[[WebSocket], Awaitable[Optional[int]]]
METHODS = Union[str, Iterable[str]]


class EndpointPatch(ContextManager):
    def __init__(self, endpoint: MockHTTPEndpoint,
                 restore_side_effect: HTTP_SIDE_EFFECT):
        self.endpoint = endpoint
        self.restore_side_effect = restore_side_effect

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.endpoint.side_effect = self.restore_side_effect
        self.endpoint.owner._raise_from_pending()


class MockHTTPEndpoint:
    def __init__(self, name: str, methods: METHODS, rule_string: str,
                 side_effect: HTTP_SIDE_EFFECT, auto_read_body: bool = True, forbid_head_verb: bool = True):
        self._request_captures: List[RecordedHTTPRequests] = []
        self.owner: Optional[WebServer] = None

        if isinstance(methods, str):
            methods = (methods,)

        self.methods: Tuple[str] = tuple(m.upper() for m in methods)
        self.rule_string = rule_string
        self.__name__ = name
        self.side_effect = side_effect
        self.auto_read_body = auto_read_body
        self.forbid_head_verb = forbid_head_verb

    def patch(self, side_effect: HTTP_SIDE_EFFECT):
        self.owner._raise_from_pending()
        previous_side_effect = self.side_effect
        self.side_effect = side_effect
        return EndpointPatch(self, previous_side_effect)

    @contextmanager
    def capture_calls(self) -> RecordedHTTPRequests:
        self.owner._raise_from_pending()
        if not self.auto_read_body:
            raise RuntimeError("cannot capture calls if auto_read_body is disabled")
        calls = RecordedHTTPRequests()
        self._request_captures.append(calls)
        yield calls
        if self._request_captures[-1] is not calls:
            raise RuntimeError('capture_calls contexts cannot be used in parallel')
        self._request_captures.pop()
        self.owner._raise_from_pending()

    async def get(self, request: Request):
        if not self.owner:
            raise RuntimeError('endpoint must be assigned to a webserver')
        if self.owner._pending_exception:
            return PlainTextResponse(
                f'an exception in the webserver had previously occurred: {self.owner._pending_exception!r}',
                status_code=HTTP_500_INTERNAL_SERVER_ERROR
            )
        if self.auto_read_body:
            await request.body()
        try:
            if isinstance(self.side_effect, Response):
                ret = self.side_effect
            else:
                ret = await self.side_effect(request)
        except Exception as ex:
            self.owner._pending_exception = ex
            return PlainTextResponse(f'handler raised an exception: {ex!r}', status_code=HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            recorded = await RecordedHTTPRequest.from_request(request)
            for c in self._request_captures:
                c.append(recorded)
        return ret

    def route(self) -> BaseRoute:
        ret = Route(self.rule_string, self.get, methods=self.methods, name=self.__name__)
        if self.forbid_head_verb and 'HEAD' not in self.methods:
            ret.methods.discard('HEAD')
        return ret


@overload
def http_endpoint(methods: METHODS, rule_string: str, *, auto_read_body: bool = True, forbid_head_verb: bool = True) \
        -> Callable[[HTTP_SIDE_EFFECT], MockHTTPEndpoint]: ...


@overload
def http_endpoint(methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *, auto_read_body: bool = True,
                  forbid_head_verb: bool = True) -> MockHTTPEndpoint: ...


def http_endpoint(methods: METHODS, rule_string: str, side_effect: Optional[HTTP_SIDE_EFFECT] = None, **kwargs):
    def ret(func: HTTP_SIDE_EFFECT):
        try:
            name = func.__name__
        except AttributeError:
            name = f'{methods} {rule_string}'
        return MockHTTPEndpoint(name, methods, rule_string, func, **kwargs)

    if side_effect is None:
        return ret
    return ret(side_effect)


class MockWSEndpoint:
    def __init__(self, name: str, rule_string: str, side_effect: WS_SIDE_EFFECT):
        self._request_captures: List[RecordedWSTranscripts] = []
        self.owner: Optional[WebServer] = None

        self.rule_string = rule_string
        self.__name__ = name
        self.side_effect = side_effect

        # this will be the endpoint handed to the starlette.WebSocketRoute.
        # the route chooses whether to hand off the scope, receive, send functions (which we need) only if we fail
        # inspect.isfunction and inspect.ismethod. Fortunately, partial fails these tests. By storing it as an
        # attribute of the endpoint, we will be able to better locate routes relating to the endpoint
        self.endpoint = partial(recorder_websocket_endpoint, func=self.get, sinks=self._request_captures)

    async def get(self, websocket: WebSocket):
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

    @contextmanager
    def capture_calls(self) -> RecordedWSTranscripts:
        self.owner._raise_from_pending()
        calls = RecordedWSTranscripts()
        self._request_captures.append(calls)
        yield calls
        if self._request_captures[-1] is not calls:
            raise RuntimeError('capture_calls contexts cannot be used in parallel')
        self._request_captures.pop()
        self.owner._raise_from_pending()


@overload
def ws_endpoint(rule_string: str) -> Callable[[WS_SIDE_EFFECT], MockWSEndpoint]: pass


@overload
def ws_endpoint(rule_string: str, side_effect: WS_SIDE_EFFECT) -> MockWSEndpoint: pass


def ws_endpoint(rule_string: str, side_effect: Optional[WS_SIDE_EFFECT] = None):
    def ret(func: WS_SIDE_EFFECT):
        return MockWSEndpoint(func.__name__, rule_string, func)

    if side_effect is None:
        return ret
    return ret(side_effect)


DEFAULT_LOG_CONFIG = deepcopy(LOGGING_CONFIG)


class WebServer(YellowService):
    def __init__(self, name: str, port: Optional[int] = None, log_config=DEFAULT_LOG_CONFIG, **kwargs):
        self._app = Starlette(debug=True)
        self._route_lock = Lock()
        # since the main thread won't catch errors in handlers, this class will store any error raised while handling,
        #  and raise them in the main thread as soon as we can
        self._pending_exception: Optional[Exception] = None
        if log_config is DEFAULT_LOG_CONFIG:
            log_config = deepcopy(DEFAULT_LOG_CONFIG)
            log_config['formatters']['access']['fmt'] = f'%(levelprefix)s {name} - "%(request_line)s" %(status_code)s'

        self.port = port or get_free_port()

        config = Config(self._app, **kwargs, port=self.port, log_config=log_config)
        self._server = Server(config)
        self._serve_thread = Thread(name=f'{name}_thread', target=self._server.run)

    @overload
    def add_http_endpoint(self, endpoint: MockHTTPEndpoint) -> MockHTTPEndpoint:
        ...

    @overload
    def add_http_endpoint(self, methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT, *,
                          auto_read_body: bool = True, forbid_head_verb: bool = True) -> MockHTTPEndpoint:
        ...

    def add_http_endpoint(self, ep: Union[METHODS, MockHTTPEndpoint], rule_string=None,
                          side_effect=None, **kwargs) -> MockHTTPEndpoint:
        self._raise_from_pending()
        if not isinstance(ep, MockHTTPEndpoint):
            if rule_string is None or side_effect is None:
                raise TypeError('both rule_string and side_effect must be provided, or an http endpoint')
            ep = http_endpoint(ep, rule_string, side_effect, **kwargs)
        elif rule_string is not None or side_effect is not None or kwargs:
            raise TypeError('cannot call with endpoint and additional parameters')
        if ep.owner is not None:
            raise RuntimeError('an endpoint cannot be added twice')
        with self._route_lock:
            self._app.routes.append(
                ep.route()
            )
        ep.owner = self
        return ep

    def remove_http_endpoint(self, endpoint: MockHTTPEndpoint):
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

    @contextmanager
    def patch_http_endpoint(self, ep: Union[METHODS, MockHTTPEndpoint], rule_string=None, side_effect=None, **kwargs):
        ep = self.add_http_endpoint(ep, rule_string, side_effect, **kwargs)
        yield http_endpoint
        self.remove_http_endpoint(ep)

    @overload
    def add_ws_endpoint(self, endpoint: MockWSEndpoint) -> MockWSEndpoint:
        ...

    @overload
    def add_ws_endpoint(self, rule_string: str, side_effect: WS_SIDE_EFFECT) -> MockWSEndpoint:
        ...

    def add_ws_endpoint(self, ep: Union[MockWSEndpoint, str], side_effect=None):
        self._raise_from_pending()
        if not isinstance(ep, MockWSEndpoint):
            if side_effect is None:
                raise TypeError('side_effect must be provided, or a websocket endpoint')
            ep = ws_endpoint(ep, side_effect)
        elif side_effect is not None:
            raise TypeError('cannot call with endpoint and additional parameters')

        if ep.owner is not None:
            raise RuntimeError('an endpoint cannot be added twice')

        with self._route_lock:
            self._app.routes.append(
                WebSocketRoute(ep.rule_string, ep.endpoint, name=ep.__name__)
            )
        ep.owner = self
        return ep

    def remove_ws_endpoint(self, endpoint: MockWSEndpoint):
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

    @contextmanager
    def patch_ws_endpoint(self, ep: Union[MockWSEndpoint, str], side_effect=None):
        ep = self.add_ws_endpoint(ep, side_effect)
        yield http_endpoint
        self.remove_ws_endpoint(ep)

    def local_url(self, schema: Optional[str] = 'http'):
        if schema is None:
            return f'localhost:{self.port}'
        return f'{schema}://localhost:{self.port}'

    def container_url(self, schema='http'):
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
        if self._pending_exception:
            pending = self._pending_exception
            self._pending_exception = None
            raise HandlerError() from pending
