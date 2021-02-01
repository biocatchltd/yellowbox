from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import re
from subprocess import Popen
from unittest.mock import Mock
from typing import Any, Callable, Generator, Optional, Pattern, List, Dict, Union, cast, no_type_check, overload
from threading import RLock
from simple_websocket_server import WebSocket, WebSocketServer
from functools import partial, wraps
from types import new_class
from weakref import WeakMethod

from yellowbox.service import YellowService


class _WebsocketTemplate(WebSocket):
    callback = None


@no_type_check
def _to_generator(side_effect: SIDE_EFFECT_TYPE
                  ) -> Callable[[BaseHTTPRequestHandler], _GENERAOTR_TYPE]:
    """Convert a side effect to a generator function.

    Args:
        side_effect: See WebsocketService.route().

    Returns:
        Generator function, same as the one in WebsocketService.route().
    """
    # Side effect == normal string
    if isinstance(side_effect, (str, bytes, bytearray, memoryview)):
        def gen(*args: Any, **kwargs: Any) -> _GENERAOTR_TYPE:
            yield side_effect
        return gen

    @wraps(side_effect)  # type: ignore # Mypy GH-10002
    def gen(*args: Any, **kwargs: Any) -> _GENERAOTR_TYPE:
        # Side effect == normal function that returns a string.
        result = side_effect(*args, **kwargs)
        if isinstance(result, (str, bytes, bytearray, memoryview)):
            yield result
        else:
            # Side effect == generator function
            return (yield from result)

    return gen


_YIELDTYPES = Union[str, bytes, bytearray, memoryview]

_GENERAOTR_TYPE = Generator[_YIELDTYPES,
                            bytearray, Any]

SIDE_EFFECT_TYPE = Union[
    _YIELDTYPES, Callable[[BaseHTTPRequestHandler], Optional[_YIELDTYPES]],
    Callable[[BaseHTTPRequestHandler], _GENERAOTR_TYPE]
]


class WebsocketService(YellowService):
    def __init__(self) -> None:
        self._routes: Dict[str, Callable] = {}
        self._re_routes: List[Pattern[str]] = []
        self._lock = RLock()

        class _WebsocketImpl(_WebsocketTemplate):
            pass
        # self._server = a

    def start(self) -> None:
        return super().start()

    def stop(self) -> None:
        return super().stop()

    def _create_websocket(self):
        pass

    def get(self, uri=None, regex=None):
        """Gets a previously added route.

        """

    def route(self, uri: Optional[str] = None, *,
              regex: Optional[Union[Pattern[str], str]] = None
              ) -> Callable[[SIDE_EFFECT_TYPE], None]:
        """Add a route.

        Raises an exception if the route already exists.

        Args:
            side_effect: Side effect can be either a string or a
            generator function.

        Raises:
        """

        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        return partial(self.add, uri=uri, regex=regex)

    def add(self, side_effect: SIDE_EFFECT_TYPE,
            uri: Optional[str] = None, *,
            regex: Optional[Union[Pattern[str], str]] = None,
            _overwrite: bool = False) -> None:
        """Add a route.

        Raises an exception if the route already exists.

        Args:
            side_effect: Side effect can be either a string or a
            generator function.

        Raises:
        """

        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        if regex:
            regex = re.compile(regex)

        gen = _to_generator(side_effect)

        # Check and place
        with self._lock:
            if not _overwrite and (uri in self._routes or
                                   regex in self._re_routes):
                raise RuntimeError(f"Route {uri or regex} already exists!")

            if uri:
                self._routes[uri] = gen
            else:
                self._re_routes.append(gen)

    def set(self, side_effect: SIDE_EFFECT_TYPE,
            uri: Optional[str] = None, *,
            regex: Optional[Union[Pattern[str], str]] = None) -> None:
        """Set a route

        Like `route()` but overwrites existing routes.
        """
        self.add(side_effect=side_effect, uri=uri,
                 regex=regex, _overwrite=True)

    def remove(self, uri: Optional[str] = None, *,
               regex: Optional[Union[Pattern[str], str]] = None) -> None:
        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        if uri:
            del self._routes[uri]
        else:
            assert regex  # For Mypy
            with self._lock:
                self._re_routes.remove(re.compile(regex))

    def clear(self) -> None:
        """Remove all routes"""
        with self._lock:
            self._routes.clear()
