from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple, Callable

from flask import Flask, Response

HandlerOutput = Union[Response, int, str, bytes, Tuple[int, Union[str, bytes]]]

@dataclass
class HTTPCall:
    method: str
    path: str
    query_params: Dict[str, List[str]]
    header: Dict[str, List[str]]
    body: Optional[bytes]


class HTTPEndPoint:
    def __init__(self):
        self.calls: List[HTTPCall] = []


class WebServer:
    def __init__(self, name: str, *args, **kwargs):
        self._flask = Flask(name, *args, **kwargs)

    def add_http_endpoint(self, handler: Callable[..., HandlerOutput], rule_string: str, **rule_options):
