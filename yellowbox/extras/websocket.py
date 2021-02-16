from __future__ import annotations
from contextlib import contextmanager

import logging

try:
    from functools import cached_property
# Support 3.7
except ImportError:
    cached_property = property  # type: ignore

import threading
from urllib.parse import urlparse
import re
from subprocess import Popen
from unittest.mock import Mock
from typing import (Any, Callable, Generator, Iterator, Optional, Pattern,  Dict,
                    Union, no_type_check, TypeVar)
from threading import RLock
from simple_websocket_server import WebSocket, WebSocketServer
from functools import partial, wraps
from weakref import WeakMethod
from yellowbox.service import YellowService
from yellowbox.utils import docker_host_name

logger = logging.getLogger(__name__)


class _WebsocketTemplate(WebSocket):
    _callback: Optional[WeakMethod] = None
    _generator: Optional[_GENERAOTR_TYPE] = None

    def connected(self) -> None:
        initialized = False
        try:
            path = urlparse(self.request.path).path
            if path is None:
                # Not supposed to happen.
                logger.warning("Message received with no path")
                return

            assert self._callback
            find_generator = self._callback()  # Resolve weakref
            assert find_generator
            generator_function = find_generator(path)

            if generator_function is None:
                logger.info(f"No handler assigned to {path}. "
                            "Closing connection.")
                return

            self._generator = generator_function(self)
            initialized = True
        except Exception:
            logger.exception("Exception raised on generator start.")
            raise

        finally:
            if not initialized:
                self.close()

        self._advance_generator()

    def _advance_generator(
            self, data: Union[bytearray, str, None] = None) -> None:
        try:
            try:
                # First one will send None, rest will send data.
                msg = self._generator.send(data)  # type: ignore
            except StopIteration as exc:
                if exc.value:
                    self.send_message(exc.value)  # May throw an exception.
                self.close()
            else:
                if msg is not None:
                    self.send_message(msg)
        except Exception:
            logger.exception("Exception raised while handling callback.")
            raise  # Handle_close will be called

    def handle(self) -> None:
        self._advance_generator(self.data)

    def handle_close(self) -> None:
        err = ConnectionAbortedError()
        generator = self._generator
        if generator is None:
            return
        del self._generator

        try:
            generator.throw(err)
        except Exception as exc:
            # Check if it's our exception. If it is, ignore it.
            if isinstance(exc, ConnectionAbortedError) and exc is err:
                return
            logger.exception("Exception raised on connection close.")
            raise
        finally:
            generator.close()  # May throw an exception. Ignore it.


@no_type_check
def _to_generator(side_effect: SIDE_EFFECT_TYPE
                  ) -> _GEN_FUNCTION_TYPE:
    """Convert a side effect to a generator function.

    Args:
        side_effect: See WebsocketService.route().

    Returns:
        Generator function, same as the one in WebsocketService.route().
    """
    # Side effect == normal string
    if isinstance(side_effect, (str, bytes, bytearray, memoryview)):
        def gen(*args: Any, **kwargs: Any) -> _GENERAOTR_TYPE:
            return side_effect
            yield  # On purpose.
        return gen

    @wraps(side_effect)  # type: ignore # Mypy GH-10002
    def gen(*args: Any, **kwargs: Any) -> _GENERAOTR_TYPE:
        # Side effect == normal function that returns a string.
        result = side_effect(*args, **kwargs)
        if result is None or isinstance(result, (str, bytes,
                                                 bytearray, memoryview)):
            return result

        # Side effect == generator function
        return (yield from result)

    return gen


##### Type aliases used all around #####
_YIELDTYPES = Union[str, bytes, bytearray, memoryview, None]

_GENERAOTR_TYPE = Generator[_YIELDTYPES,
                            Union[bytearray, str], _YIELDTYPES]

_GEN_FUNCTION_TYPE = Callable[[WebSocket], _GENERAOTR_TYPE]

SIDE_EFFECT_TYPE = Union[
    _YIELDTYPES, Callable[[WebSocket], Optional[_YIELDTYPES]],
    _GEN_FUNCTION_TYPE
]

_T = TypeVar("_T")
########################################


class WebsocketService(YellowService):
    def __init__(self) -> None:
        self._routes: Dict[str, Callable] = {}
        self._re_routes: Dict[Pattern[str], Callable] = {}
        self._lock = RLock()
        _stop_event = self._stop_event = threading.Event()

        class _WebsocketImpl(_WebsocketTemplate):
            _callback = WeakMethod(self._get_callback)  # type: ignore

        server = self._server = WebSocketServer("0.0.0.0", 0, _WebsocketImpl)

        # serve_forever() doesn't let you close the server without throwing
        # an exception >.<
        def loop() -> None:
            while not _stop_event.is_set():
                server.handle_request()

        self._thread = threading.Thread(target=loop, daemon=True)

    @cached_property
    def port(self) -> int:
        return self._server.serversocket.getsockname()[1]

    @cached_property
    def local_url(self) -> str:
        return f'ws://127.0.0.1:{self.port}'

    @cached_property
    def container_url(self) -> str:
        return f'ws://{docker_host_name}:{self.port}'

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    # Mypy doesn't support self generics yet without manual binding (bound=)
    # https://mypy.readthedocs.io/en/stable/generics.html#generic-methods-and-generic-self
    @no_type_check
    def start(self: _T) -> _T:
        self._thread.start()
        return super().start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(1)
        self._server.close()
        return super().stop()

    def _get_callback(self, path: str) -> Union[_GEN_FUNCTION_TYPE, None]:
        callback = self._routes.get(path)
        if callback:
            return callback

        items = reversed(tuple(self._re_routes.items()))  # Thread safety
        for pattern, callback in items:
            if pattern.fullmatch(path):
                return callback

        return None

    def route(self, uri: Optional[str] = None, *,
              regex: Optional[Union[Pattern[str], str]] = None
              ) -> Callable[[SIDE_EFFECT_TYPE], None]:
        """Add a route.

        Raises an exception if the route already exists.

        Args:
            side_effect: Side effect can be either a string or a
            generator function.
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
            RuntimeError: Trying to add a route while it already exists.
        """
        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        if regex:
            regex = re.compile(regex)
        elif not isinstance(uri, str):
            # Prevent variable order confusion.
            raise TypeError("URI must be a string.")

        gen = _to_generator(side_effect)

        # Check and place
        with self._lock:
            if not _overwrite and (uri in self._routes or
                                   regex in self._re_routes):
                raise RuntimeError(f"Route {uri or regex} already exists!")

            if uri:
                self._routes[uri] = gen
            else:
                self._re_routes[regex] = gen  # type: ignore

    @contextmanager
    def patch(self, side_effect: SIDE_EFFECT_TYPE,
              uri: Optional[str] = None, *,
              regex: Optional[Union[Pattern[str], str]] = None) -> Iterator[None]:
        """Temporarily patch a route.

        Raises an exception if the route already exists.

        Args:
            Same as add().
        """
        self.add(side_effect, uri, regex=regex)
        try:
            yield
        finally:
            self.remove(uri, regex=regex)

    def set(self, side_effect: SIDE_EFFECT_TYPE,
            uri: Optional[str] = None, *,
            regex: Optional[Union[Pattern[str], str]] = None) -> None:
        """Set a route.

        Like `add()` but overwrites existing routes.
        """
        self.add(side_effect=side_effect, uri=uri,
                 regex=regex, _overwrite=True)

    def remove(self, uri: Optional[str] = None, *,
               regex: Optional[Union[Pattern[str], str]] = None) -> None:
        """Remove a route."""
        if uri and regex:
            raise ValueError("Only one of URI or regex can be specified.")

        if not (uri or regex):
            raise ValueError("URI or regex must be specified.")

        if uri:
            del self._routes[uri]
        else:
            assert regex  # For Mypy
            regex = re.compile(regex)
            with self._lock:
                del self._re_routes[regex]

    def clear(self) -> None:
        """Remove all routes."""
        with self._lock:
            self._routes.clear()
            self._re_routes.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create a simple echo websocket server
    server = WebsocketService()

    @server.route(regex=".*")
    def echo(websocket):
        data = None
        while True:
            data = yield data

    print("Starting echo websocket server...")
    server.start()
    print(f"Server started at {server.local_url}. Press Ctrl+C to stop.")
    import signal
    try:
        try:
            signal.pause()
        except AttributeError:
            pass
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping server...")
        server.stop()
