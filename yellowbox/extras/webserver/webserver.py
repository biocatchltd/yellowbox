from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from logging import StreamHandler, DEBUG
from os import environ
from threading import Lock, Thread
from time import sleep
from typing import List, Union, Iterable, Optional, Callable

from flask import Flask, Request, request
from flask.typing import ResponseReturnValue
from requests import post, get, HTTPError, ConnectionError
from werkzeug.serving import BaseWSGIServer, make_server

from yellowbox.retry import RetrySpec

from yellowbox import YellowService
from yellowbox.utils import get_free_port, docker_host_name


class HandlerError(Exception):
    """
    An exception occurred while handling an endpoint in the webserver thread
    """

    @classmethod
    def raise_from_pending(cls, pending: Optional[Exception]):
        if pending:
            raise cls() from pending


class HTTPEndPoint(ABC):
    def __init__(self, name: str, methods: Union[str, Iterable[str]], rule_string: str, **rule_options):
        self._calls: List[Request] = []
        self.owner: Optional[WebServer] = None

        if isinstance(methods, str):
            methods = (methods,)

        self.methods: Iterable[str] = tuple(methods)
        self.rule_string = rule_string
        self.rule_options = rule_options
        self.__name__ = name

    @abstractmethod
    def handle(self, **kwargs) -> ResponseReturnValue:
        pass

    @contextmanager
    def capture_calls(self):
        HandlerError.raise_from_pending(self.owner._pending_exception)
        self._calls.clear()
        yield self._calls
        HandlerError.raise_from_pending(self.owner._pending_exception)

    def __call__(self, *args, **kwargs):
        if not self.owner:
            raise RuntimeError('endpoint must be assigned to a webserver')
        with self.owner._route_lock:
            if self.owner._pending_exception:
                return f'an exception in the webserver had previously occurred: {self.owner._pending_exception!r}', 500
            try:
                ret = self.handle(**kwargs)
            except Exception as ex:
                self.owner._pending_exception = ex
                return f'handler raised an exception: {ex!r}'
            else:
                self._calls.append(request)
            return ret


class MockHTTPEndpoint(HTTPEndPoint):
    def __init__(self, *args, side_effect: Union[ResponseReturnValue, Callable[..., ResponseReturnValue]], **kwargs):
        super().__init__(*args, **kwargs)
        self.side_effect = side_effect

    def handle(self, **kwargs) -> ResponseReturnValue:
        if callable(self.side_effect):
            return self.side_effect(**kwargs)
        return self.side_effect

    @contextmanager
    def patch(self, side_effect: Union[ResponseReturnValue, Callable[..., ResponseReturnValue]]):
        previous_side_effect = self.side_effect
        self.side_effect = side_effect
        yield
        self.side_effect = previous_side_effect


class WebServer(YellowService):
    def __init__(self, name: str, port: int = 0, log_level: Optional[int] = None, poll_interval: float = 0.1, *args,
                 **kwargs):
        self._flask = Flask(name, *args, **kwargs)
        self._route_lock = Lock()
        # since the main thread won't catch errors in handlers, this class will store any error raised while handling,
        #  and raise them in the main thread as soon as we can
        self._pending_exception: Optional[Exception] = None

        self._server: BaseWSGIServer = make_server('127.0.0.1', port, self._flask)
        self._serve_thread = Thread(name=f'{self._flask.name}_thread',
                                    target=lambda: self._server.serve_forever(poll_interval))

        self.port = self._server.server_port

        if log_level is not None:
            self._flask.logger.setLevel(log_level)
            self._flask.logger.addHandler(StreamHandler())
            if 0 < log_level <= DEBUG:
                @self._flask.after_request
                def after_request(response):
                    self._flask.logger.error(
                        f'{request.remote_addr} {request.method} {request.scheme} {request.full_path} {response.status}'
                    )
                    return response

    def add_http_endpoint(self, endpoint: HTTPEndPoint) -> HTTPEndPoint:
        with self._route_lock:
            self._flask.add_url_rule(endpoint.rule_string, view_func=endpoint)
            endpoint.owner = self
            return endpoint

    def remove_endpoint(self, endpoint: HTTPEndPoint):
        with self._route_lock:
            del self._flask.view_functions[endpoint.__name__]
            new_rules = []
            rules_to_remove = []
            for rule in self._flask.url_map._rules:
                if rule.rule == endpoint.rule_string:
                    rules_to_remove.append(rule)
                else:
                    new_rules.append(rule)
            self._flask.url_map._rules = new_rules

            seen_endpoints = set()
            for rule in rules_to_remove:
                if rule.endpoint in seen_endpoints:
                    continue
                seen_endpoints.add(rule.endpoint)
                lst = self._flask.url_map._rules_by_endpoint.get(rule.endpoint)
                if lst is None:
                    continue
                lst[:] = [rule for rule in lst if rule not in rules_to_remove]

            self._remap = True

    @contextmanager
    def patch_endpoint(self, endpoint: HTTPEndPoint):
        HandlerError.raise_from_pending(self._pending_exception)
        self.add_http_endpoint(endpoint)
        yield endpoint
        self.remove_endpoint(endpoint)
        HandlerError.raise_from_pending(self._pending_exception)

    def local_url(self, schema: Optional[str]='http'):
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
        self._serve_thread.start()
        with self.patch_endpoint(MockHTTPEndpoint('admin-ping', 'GET', '/__yellowbox/ping', side_effect='')):
            retry_spec = retry_spec or RetrySpec(attempts=3)
            retry_spec.retry(
                lambda: get(self.local_url() + '/__yellowbox/ping').raise_for_status(),
                (ConnectionError, HTTPError)
            )
        return super().start()

    def stop(self):
        self._server.shutdown()
        self._serve_thread.join()
        super().stop()
        HandlerError.raise_from_pending(self._pending_exception)

    def is_alive(self) -> bool:
        HandlerError.raise_from_pending(self._pending_exception)
        return self._serve_thread.is_alive()
