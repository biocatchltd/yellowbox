import re
from unittest.mock import Mock
from threading import Lock
from simple_websocket_server import WebSocket, WebSocketServer

from yellowbox.service import YellowService


class WebsocketImpl:
    service = None


class WebsocketService(YellowService):
    def __init__(self):
        self._routes = {}
        self._lock = Lock()
        self._server = a

    def start(self):
        pass

    def stop(self):
        pass

    def _create_websocket(self):
        pass

    def route(self, uri=None, side_effect=None, *, regex=None):
        """Add a route.

        Args:
            side_effect: Side effect can be either a string or a
            generator function.
        """

        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        # Allow decorator syntax
        if not side_effect:
            return partial(self.respond, uri=uri, regex=regex)

    def remove(self, uri=None, *, regex=None):
        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        with self._lock:
            del self._routes[uri or re.compile(regex)]

    def clear(self):
        """Remove all routes"""
        with self._lock:
            self._routes.clear()
