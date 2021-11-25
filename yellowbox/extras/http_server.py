from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock, Thread
from types import new_class
from typing import Callable, ClassVar, DefaultDict, List, Mapping, NamedTuple, Optional, Pattern, Set, Type, Union, cast
from urllib.parse import ParseResult, parse_qs, urlparse

import requests
from requests import ConnectionError, HTTPError

from yellowbox.retry import RetrySpec
from yellowbox.service import YellowService
from yellowbox.utils import docker_host_name

__all__ = ['HttpService', 'RouterHTTPRequestHandler']
SideEffectResponse = Union[bytes, str, int, 'RouterHTTPRequestHandler']
SideEffect = Union[Callable[['RouterHTTPRequestHandler'], SideEffectResponse],
                   SideEffectResponse]


class RoutedHandler(NamedTuple):
    method: str
    name: str
    route: Union[Pattern[str], str]
    callback: Callable[[RouterHTTPRequestHandler], None]

    def route_match(self, path: str):
        if isinstance(self.route, str):
            return self.route == path
        return self.route.fullmatch(path)


class RouterHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    A BaseHTTPRequestHandler that allows adding and deleting routed handlers.
    Also contains some utility argument parsing.
    """
    _parse_url: ParseResult
    _body: Optional[bytes]

    routes_by_method: ClassVar[DefaultDict[str, Set[RoutedHandler]]]
    route_lock: ClassVar[Lock]

    def body(self) -> Optional[bytes]:
        try:
            return self._body
        except AttributeError:
            raw_body_len = self.headers['Content-Length']
            if raw_body_len is None:
                self._body = None
            else:
                length = int(raw_body_len)
                self._body = self.rfile.read(length)
            return self._body

    def path_params(self, **kwargs) -> Mapping[str, List[str]]:
        """
        Extract the path parameters from the query
        Args:
            **kwargs: forwarded to urllib.parse.parse_qs

        Returns:
            A mapping from parameter name to a list of values provided

        """
        parsed = self.parse_url()
        return parse_qs(parsed.query, **kwargs)

    def parse_url(self) -> ParseResult:
        try:
            return self._parse_url
        except AttributeError:
            self._parse_url = urlparse(self.path)
            return self._parse_url

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.routes_by_method = defaultdict(set)
        cls.route_lock = Lock()

    @classmethod
    def add_route(cls, handler: RoutedHandler):
        with cls.route_lock:
            cls.routes_by_method[handler.method].add(handler)

    @classmethod
    def del_route(cls, handler: RoutedHandler):
        with cls.route_lock:
            cls.routes_by_method[handler.method].remove(handler)

    def _do(self):
        """
        A generic handler for all http methods.
        Filters through all added routes and calls the appropriate callback, if one is found.
        """
        parsed = self.parse_url()

        candidates = tuple(self.routes_by_method.get(self.command, ()))
        matched_candidates = []
        for candidate in candidates:
            match = candidate.route_match(parsed.path)
            if match:
                matched_candidates.append((candidate, match))
        if not matched_candidates:
            self.send_error(404, 'mock server matched no routes')
            self.end_headers()
        elif len(matched_candidates) > 1:
            self.send_error(500, 'mock server matched multiple routes: '
                            + ', '.join(c.name for c, _ in matched_candidates))
            self.end_headers()
        else:
            (routed, match), = matched_candidates
            self.log_message(f'routed to {routed.name}')
            self.match = match
            routed.callback(self)

    def __getattr__(self, item: str):
        if item.startswith('do_'):
            return self._do
        raise AttributeError(item)


class HttpService(YellowService):
    """
    The HttpService class is used to mock http servers. Although it is a YellowService,
    it does not wrap a docker container, rather, it wraps a standard library HTTPServer, with a server
    thread running in the background. The server uses an internal router that maps paths to callbacks.

    Example usage:
    >>> with HttpService().start() as service:
    ...   @service.patch_route('GET', '/hello/world')
    ...   def hello_world(handler: RouterHTTPRequestHandler):
    ...      return "hi there"
    ...   # hello_world is now a context manager
    ...   with hello_world:
    ...      # within this scope, the path "/hello/world" will return a 200 response with the body "hi there"
    ...      assert requests.get(service.local_url+"/hello/world").text == "hi there"
    ...   # routes can also be set without a function
    ...   with service.patch_route('GET', '/meaning_of_life', '42'):
    ...      assert requests.get(service.local_url+"/meaning_of_life").content == b'42'
    """

    def __init__(self, host='0.0.0.0', port=0, name='anonymous_yellowbox_HTTPService'):
        self.router_cls = cast(Type[RouterHTTPRequestHandler],
                               new_class(name + '_RequestHandler', (RouterHTTPRequestHandler,)))
        self.server = HTTPServer((host, port), self.router_cls)
        self.server_thread = Thread(name=name + '_thread', target=self.server.serve_forever,
                                    daemon=True)

    @property
    def server_port(self):
        return self.server.server_port

    @property
    def local_url(self):
        return f'http://127.0.0.1:{self.server_port}'

    @property
    def container_url(self):
        return f'http://{docker_host_name}:{self.server_port}'

    @staticmethod
    def _to_callback(side_effect: SideEffect):
        def _respond(handler: RouterHTTPRequestHandler, response: SideEffectResponse):
            if response is handler:
                return  # Assuming the user already handled the response
            if isinstance(response, int):
                handler.send_error(response)
                handler.end_headers()
                return
            handler.send_response(200)
            handler.end_headers()
            if isinstance(response, str):
                response = bytes(response, 'ascii')
            if isinstance(response, bytes):
                handler.wfile.write(response)
            else:
                raise TypeError(f"got response of type {type(response)}, type must be RouterHTTPRequestHandler, "
                                f"int, str or bytes")

        def callback(handler: RouterHTTPRequestHandler):
            if callable(side_effect):
                result = side_effect(handler)
                _respond(handler, result)
            else:
                _respond(handler, cast(SideEffectResponse, side_effect))

        return callback

    def patch_route(self, method, route: Union[str, Pattern[str]],
                    side_effect: SideEffect = ...,  # type: ignore[assignment]
                    name: Optional[str] = None):
        """
        Create a context manager that temporarily adds a route handler to the service.

        Args:
            method: The request method to add the route to.
            route: The route to attach the side effect to, all routes must begin with a slash "/".
                Alternatively, The route may be a regex pattern, in which case the request path must fully match it,
                the match object is then stored in RouterHTTPRequestHandler.match, to be used by a side-effect callable.
            side_effect: The callback or result to return for the route. Accepts any of the following types:
                * int: to return the value as the HTTP status code, without a body.
                * bytes: to return 200, with the value as the response body.
                * str: invalid if the value is non-ascii, return 200 with the value, translated to bytes, as
                 the response body.
                * callable: Must accept a RouterHTTPRequestHandler. May return any of the above types, or
                  RouterHTTPRequestHandler to handle the response directly with the RouterHTTPRequestHandler.
            name:
                An optional name for the routed handler, to be used while logging. If missing, a suitable name is
                extracted from the side effect or route.

        Returns:
            A context manager that will enable the route upon entry and disable it upon exit.

        Notes:
            This method can be used as a decorator by not specifying `side_effect`
        """
        if side_effect is ...:
            return partial(self.patch_route, method, route, name=name)

        @contextmanager
        def _helper():
            nonlocal name
            callback = self._to_callback(side_effect)
            name = name or getattr(side_effect, '__name__', None) or str(route)
            handler = RoutedHandler(method, name, route, callback)
            self.router_cls.add_route(handler)
            try:
                yield handler
            finally:
                self.router_cls.del_route(handler)

        return _helper()

    def start(self, retry_spec: Optional[RetrySpec] = None):
        with self.patch_route('GET', '/health', 200):
            self.server_thread.start()
            retry_spec = retry_spec or RetrySpec(attempts=10)
            retry_spec.retry(
                lambda: requests.get(self.local_url + '/health').raise_for_status(),
                (ConnectionError, HTTPError)
            )
        return super(HttpService, self).start()

    def stop(self):
        self.server.shutdown()
        self.server_thread.join()

    def is_alive(self):
        return self.server_thread.is_alive()
