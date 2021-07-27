from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Union, Iterable, Optional

from flask import Flask, Response, Request
from flask.typing import ResponseReturnValue

HandlerOutput = Union[ResponseReturnValue, int]

class HandlerError(Exception):
    """
    An exception occurred while handling an endpoint in the webserver thread
    """
    pass

class ExceptionCell:
    # since the main thread won't catch errors in handlers, this class will store any error raised while handling,
    #  and raise them in the main thread as soon as we can
    def __init__(self):
        self.exc : Optional[Exception] = None

    def raise_if_error(self):
        if self.is_error():
            raise self.exc

    def is_error(self)->bool:
        return self.exc is not None

class HTTPEndPoint(ABC):
    owner: WebServer

    def __init__(self, methods: Union[str, Iterable[str]], rule_string: str, **rule_options):
        self._calls: List[Request] = []


        if isinstance(methods, str):
            methods = (methods,)

        self.methods: Iterable[str] = tuple(methods)
        self.rule_string = rule_string
        self.rule_options = rule_options

    @abstractmethod
    def handle(self, **kwargs) -> HandlerOutput:
        pass

    def view_func(self, **kwargs):
        if not hasattr(self, 'owner'):
            raise RuntimeError('endpoint must be assigned to a webserver')
        if self.owner.exception_cell.is_error():
            return f'an exception in the webserver had previously occurred: {self.owner.exception_cell.exc!r}', 500
        try:
            ret = self.handle(**kwargs)
        except Exception as ex:
            self.owner.exception_cell.exc = ex
            return f'handler raised an exception: {ex!r}'
        else:

        return ret


class WebServer:
    def __init__(self, name: str, *args, **kwargs):
        self._flask = Flask(name, *args, **kwargs)
        self.exception_cell = ExceptionCell()

    def add_http_endpoint(self, endpoint: HTTPEndPoint):
        self._flask.add_url_rule(endpoint.rule_string, methods=endpoint.methods, view_func=endpoint.view_func)
