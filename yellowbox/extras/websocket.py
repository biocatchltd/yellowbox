from __future__ import annotations

import logging
from contextlib import contextmanager

try:
    from functools import cached_property  # type: ignore
# Support 3.7
except ImportError:
    cached_property = property  # type: ignore

import re
import threading
from functools import partial, wraps
from threading import RLock
from typing import (
    Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Pattern, TypeVar, Union, no_type_check
)
from urllib.parse import urlparse
from weakref import WeakMethod

from simple_websocket_server import WebSocket, WebSocketServer

from yellowbox.service import YellowService
from yellowbox.utils import docker_host_name

logger = logging.getLogger(__name__)


class _WebsocketTemplate(WebSocket):
    """Template websocket protocol.

    Used in WebSocketServer, this class handles incoming connections and
    communicates over a generator to send and receive data. See WebsocketService
    for usage.
    """
    _get_generator: Optional[WeakMethod] = None
    """
    A weakmethod to call WebsocketService._get_generator and find the
    generator appropriate for the connected websocket path.
    """
    _generator: "Optional[_GENERAOTR_TYPE]" = None
    """An initialized generator for IO with the websocket"""

    def connected(self) -> None:
        """Websocket connected callback.

        Finds the correct generator for IO with this websocket and sets it
        up.
        """
        initialized = False
        try:
            path = urlparse(self.request.path).path
            if path is None:
                # Not supposed to happen.
                logger.warning("Message received with no path")
                return

            assert self._get_generator
            get_generator = self._get_generator()  # Resolve weakref
            assert get_generator
            generator_function = get_generator(path)

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

        self._advance_generator(None)

    def _advance_generator(
            self, data: Union[bytearray, str, None]) -> None:
        """Advance the IO generator. Send it data and wait for output."""
        try:
            try:
                # First one will send None, rest will send data.
                msg = self._generator.send(data)  # type: ignore
            except StopIteration as exc:
                if exc.value:  # type: ignore
                    # Sending may throw an exception.
                    self.send_message(exc.value)  # type: ignore
                self.close()
            else:
                if msg is not None:
                    self.send_message(msg)
        except Exception:
            logger.exception("Exception raised while handling callback.")
            raise  # Handle_close will be called

    def handle(self) -> None:
        """Incoming data callback."""
        self._advance_generator(self.data)

    def handle_close(self) -> None:
        """Connection closed callback."""
        err = ConnectionAbortedError()
        generator = self._generator

        # Closed before full initialization
        if generator is None:
            return
        del self._generator

        try:
            generator.throw(err)
        except Exception as exc:
            # Check if it's our exception. If it is, ignore it.
            if exc is err:
                return
            logger.exception("Exception raised on connection close.")
            raise
        finally:
            generator.close()  # May throw an exception. Ignore it.


@no_type_check
def _to_generator(
        side_effect: SIDE_EFFECT_TYPE) -> _GEN_FUNCTION_TYPE:
    """Convert a side effect to an IO generator function.

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

    # Side effect == list of strings
    if isinstance(side_effect, Iterable):
        def gen(*args, **kwargs) -> _GENERAOTR_TYPE:
            for item in side_effect:
                yield item
        return gen

    assert callable(side_effect)

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


# Type aliases used all around
_YIELDTYPES = Union[str, bytes, bytearray, memoryview, None]

_GENERAOTR_TYPE = Generator[_YIELDTYPES,
                            Union[bytearray, str], _YIELDTYPES]

_GEN_FUNCTION_TYPE = Callable[[WebSocket], _GENERAOTR_TYPE]

SIDE_EFFECT_TYPE = Union[
    _YIELDTYPES, List[_YIELDTYPES],
    Callable[[WebSocket], Optional[_YIELDTYPES]],
    _GEN_FUNCTION_TYPE
]

_T = TypeVar("_T")


class WebsocketService(YellowService):
    """Yellobox service to handle incoming websocket connections.

    Allows 2 sided communication using different kinds of side effects.
    Non-blocking, all side effects are ran in a different thread.

    Example:
        >>> service = WebsocketService()

        Let's write "Hello!" to the websocket upon connection to the "/hello"
        endpoint:
        >>> service.add("Hello!", "/hello")

        We'll also make a simple echo endpoint:
        >>> @service.route("/echo")
        ... def echo(websocket):
        ...     data = None
        ...     while True:
        ...         # Yield sends out the data, and waits for incoming data.
        ...         data = yield data
        ...

        And start our service!
        >>> service.start()

        Keep in mind it's non-blocking. The service will run in the background.

        An local websocket should connect to `service.local_url` or
        `service.container_url` if communicating with a hosted docker
        container.
    """
    port: int
    """Server listening port."""

    def __init__(self) -> None:
        """Initialize the service."""
        self._routes: Dict[str, Callable] = {}
        self._re_routes: Dict[Pattern[str], Callable] = {}
        self._lock = RLock()
        _stop_event = self._stop_event = threading.Event()

        class _WebsocketImpl(_WebsocketTemplate):
            _get_generator = WeakMethod(self._get_generator)  # type: ignore

        server = self._server = WebSocketServer("0.0.0.0", 0, _WebsocketImpl)
        self.port = server.serversocket.getsockname()[1]

        # serve_forever() doesn't let you close the server without throwing
        # an exception >.<
        def loop() -> None:
            while not _stop_event.is_set():
                server.handle_request()

        self._thread = threading.Thread(target=loop, daemon=True)

    @cached_property
    def local_url(self) -> str:
        """Local URL for connecting on the same host.

        Suffix this with the path. For example, if you wish to connect locally
        to the "/echo" endpoint, connect to `service.local_url + '/echo'`.
        """
        return f'ws://127.0.0.1:{self.port}'

    @cached_property
    def container_url(self) -> str:
        """URL for connecting over a locally hosted docker container.

        Suffix this with the path. For example, if you wish to connect to the
        "/echo" endpoint from inside a container, connect
        to `service.container_url + '/echo'`.
        """
        return f'ws://{docker_host_name}:{self.port}'

    def is_alive(self) -> bool:
        """Boolean stating if wesocket service is active."""
        return self._thread.is_alive()

    # Mypy doesn't support self generics yet without manual binding (bound=)
    # https://mypy.readthedocs.io/en/stable/generics.html#generic-methods-and-generic-self
    @no_type_check
    def start(self: _T) -> _T:
        """Start the service.

        Non-blocking. Service runs in the background.
        """
        self._thread.start()
        return super().start()

    def stop(self) -> None:
        """Stop the service."""
        self._stop_event.set()
        self._thread.join(1)

        # Shouldn't actually happen.
        if self._thread.is_alive():
            logger.error("Failed to stop the service gracefully. Timed out.")

        self._server.close()
        return super().stop()

    def _get_generator(self, path: str) -> Union[_GEN_FUNCTION_TYPE, None]:
        """Get the IO generator function appropriate to the connected path.

        Args:
            path: Websocket path.

        Returns:
            Generator function, or None if not found.
        """
        callback = self._routes.get(path)
        if callback:
            return callback

        items = reversed(tuple(self._re_routes.items()))  # Thread safety
        for pattern, callback in items:
            if pattern.fullmatch(path):
                return callback

        return None

    def route(self, path: Optional[str] = None, *,
              regex: Optional[Union[Pattern[str], str]] = None
              ) -> Callable[[SIDE_EFFECT_TYPE], None]:
        """Add a route using a decorator syntax.

        Raises an exception if the route already exists.

        Example:

            >>> @service.route("/echo")
            ... def echo(websocket):
            ...     data = None
            ...     while True:
            ...         # Yield sends out the data, and waits for incoming data.
            ...         data = yield data
            ...

        Args:
            path: path to accept connections on. Omit if using regex.
            regex: path regex to accept connections on. Omit if using path.

        Returns:
            Decorator for adding a side effect as a route.
        """
        if path and regex:
            raise ValueError("Only one of path or regex can be specified.")

        if not (path or regex):
            raise ValueError("path or regex must be specified.")

        return partial(self.add, path=path, regex=regex)

    def add(self, side_effect: SIDE_EFFECT_TYPE,
            path: Optional[str] = None, *,
            regex: Optional[Union[Pattern[str], str]] = None,
            _overwrite: bool = False) -> None:
        """Add a route.

        Raises an exception if the route already exists.

        Args:
            side_effect: Side effect can be either a string, bytes or bytearray
            to return a single message; iterable of any combination of them to
            return multiple messages; A regular function that returns any of them
            that will be called upon receiving an incoming connection; or a
            generator function that yields any of them and accepts data. For
            more information see the examples above.
            path: path to accept connections on. Omit if using regex.
            regex: path regex to accept connections on. Omit if using path.

        Raises:
            RuntimeError: Trying to add a route while it already exists.
        """
        if path and regex:
            raise ValueError("Only one of path or regex can be specified.")

        if not (path or regex):
            raise ValueError("path or regex must be specified.")

        if regex:
            regex = re.compile(regex)
        elif not isinstance(path, str):
            # Prevent variable order confusion.
            raise TypeError("path must be a string.")

        gen = _to_generator(side_effect)

        # Check and place
        with self._lock:
            if not _overwrite and (path in self._routes or
                                   regex in self._re_routes):
                raise RuntimeError(f"Route {path or regex} already exists!")

            if path:
                self._routes[path] = gen
            else:
                self._re_routes[regex] = gen  # type: ignore

    @contextmanager
    def patch(self, side_effect: SIDE_EFFECT_TYPE,
              path: Optional[str] = None, *,
              regex: Optional[Union[Pattern[str], str]] = None) -> Iterator[None]:
        """Temporarily patch a route.

        Like `.add()` but uses a context manager for easy removal.
        """
        self.add(side_effect, path, regex=regex)
        try:
            yield
        finally:
            self.remove(path, regex=regex)

    def set(self, side_effect: SIDE_EFFECT_TYPE,
            path: Optional[str] = None, *,
            regex: Optional[Union[Pattern[str], str]] = None) -> None:
        """Set a route.

        Like `add()` but overwrites existing routes.
        """
        self.add(side_effect=side_effect, path=path,
                 regex=regex, _overwrite=True)

    def remove(self, path: Optional[str] = None, *,
               regex: Optional[Union[Pattern[str], str]] = None) -> None:
        """Remove a route.

        Args:
            path: Path that was previously inserted. Omit if using regex.
            regex: Regex that was previously inserted. Omit if using path.
        """
        if path and regex:
            raise ValueError("Only one of path or regex can be specified.")

        if not (path or regex):
            raise ValueError("path or regex must be specified.")

        if path:
            del self._routes[path]
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
