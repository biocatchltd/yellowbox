from __future__ import annotations

import json
import logging
import selectors
import socket
import threading
from typing import Any, Callable, Dict, Iterator, List, Union, cast
from weakref import WeakMethod

from yellowbox.subclasses import YellowService
from yellowbox.utils import docker_host_name

__all__ = ["FakeLogstashService"]
_logger = logging.getLogger(__name__)

_STOP_TIMEOUT = 5  # Timeout for stopping the service

# Sent on internal connection to signal closing of background thread
_CLOSE_SENTINEL = b"\0"


def _level_to_int(level: Union[str, int]) -> int:
    """Convert a log level in str or int into an int.

    Args:
        level: Can be a string or int

    Returns:
        level as int.
    """
    if not isinstance(level, int):
        level = logging.getLevelName(level.upper())

    # In rare cases it might be false, but it shouldn't generally happen.
    if not isinstance(level, int):
        raise ValueError(f"Unknown level {level!r}.")

    return level


class FakeLogstashService(YellowService):
    """Implements a fake logging service that closely resembles Logstash.

    Accepts external TCP connections, with logs received in the "json_lines"
    format.

    Attributes:
        records: A list of all records received. You are welcome to modify,
        clear or iterate over this during runtime. New logs will be added in the
        order they were received. Each record is a dict - for possible keys see
        attribute docs.
        port: Dynamic port external service should connect to. FakeLogstashService
        automatically binds a free port during initialization unless chosen
        otherwise.
        local_host: Host to connect to from the local machine (=="localhost")
        container_host: Host to connect to from inside containers.
        encoding: Encoding of the json lines received. Defaults to utf-8 per
        specification.
        delimiter: Delimiter splitting between json objects. Defaults to b'\n'
        per specification.

    Example:
        >>> import socket
        >>> import time
        >>> ls = FakeLogstashService()
        >>> ls.start()
        >>> # Logstash Handler internally creates this connection and sends a log.
        >>> s = socket.create_connection((ls.local_host, ls.port))
        >>> s.sendall(b'{"record": "value", "level": "ERROR"}\\n')
        >>> s.close()
        >>> time.sleep(0.01)  # Wait for service to process message
        >>> ls.stop()
        >>> ls.assert_logs("ERROR")
        >>> assert ls.records[0]["record"] == "value"
    """

    delimiter: bytes = b"\n"
    encoding: str = "utf-8"
    local_host: str = "localhost"
    container_host: str = docker_host_name

    def __init__(self, port: int = 0) -> None:
        """Initialize the service.

        Args:
            port: Port to listen on. By default or if set to 0, port is chosen
            by the OS.
        """

        self.records: List[Dict[str, Any]] = []
        """
        Records generated by Python's numerous Logstash packages have at least the
        following keys in common:
            * @timestamp: str - Log timestamp in ISO-8601 format.
            * @version: str - Logstash format version (always 1)
            * message: str - Log message.
            * host: str - Host sending the message.
            * path: str - Path to the module writing the log.
            * tags: List[str] - ?
            * type: str - "Logstash"
            * level: str - An all upper-case name of the log level
            * logger_name: str - Logger name
            * stack_info: Optional[str] - Formatted stacktrace if one exists.

        More keys may be added by the specific software sending the logs.
        """

        root = socket.socket()
        root.bind(("0.0.0.0", port))
        self._root = root

        # Avoiding a cyclic reference.
        _background = WeakMethod(self._background_thread)
        self._thread = threading.Thread(target=lambda: _background()(), daemon=True)

        self._selector = selectors.DefaultSelector()

        # Sockets used for signalling shutdown
        self._rshutdown, self._wshutdown = socket.socketpair()

        self.port: int = self._root.getsockname()[1]

    def __del__(self):
        # Will never happen while thread is running.
        try:
            # Order is important.
            self._root.close()
            self._selector.close()
            self._rshutdown.close()
            self._wshutdown.close()
        except AttributeError:  # pragma: no cover  # Hard and pointless to test.
            pass

    def _create_data_callback(self, sock: socket.socket) -> Callable[[], None]:
        """Creates a callback to be called every time the socket receives data.

        Args:
            sock: A connected socket.socket().

        Returns:
            A callable that should be called every time the socket receives data.
        """
        # Data chunks received while waiting for a delimiter.
        partial_chunks = []
        delimiter = self.delimiter
        encoding = self.encoding

        def process_socket_data():
            """Process & parse incoming socket data."""
            data = sock.recv(1024)

            # Socket closed
            if not data:
                self._selector.unregister(sock)
                return

            chunks = data.split(delimiter)

            # Single partial chunk (no delimiter)
            # todo: Cap max chunks length. Not a security issue as we're using
            # todo: Yellowbox solely for testing.
            if len(chunks) == 1:
                partial_chunks.append(chunks[0])
                return

            # Combine all partial chunks with first.
            partial_chunks.append(chunks[0])
            chunks[0] = b"".join(partial_chunks)
            partial_chunks[:] = [chunks.pop()]

            chunk = b""  # Linters are stupid. Required for it to pass.

            # Parse all chunks into records.
            try:
                for chunk in chunks:
                    record_dict = json.loads(chunk.decode(encoding))
                    self.records.append(record_dict)
            except json.JSONDecodeError:
                self._selector.unregister(sock)
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                _logger.exception("Failed decoding json, closing socket. Data received: %s", chunk)
                return

        return process_socket_data

    def _background_thread(self):
        """Background thread processing incoming connections and data"""
        while True:
            events = self._selector.select(timeout=5)  # For signal handling
            for key, _mask in events:
                # Handle closing request
                if key.fileobj is self._rshutdown:
                    assert self._rshutdown.recv(len(_CLOSE_SENTINEL)) == _CLOSE_SENTINEL
                    return

                # Handle new connection
                if key.fileobj is self._root:
                    new_socket, _ = self._root.accept()
                    self._selector.register(new_socket, selectors.EVENT_READ, self._create_data_callback(new_socket))
                    continue

                # Data received, run callback
                try:
                    key.data()
                except Exception:
                    _logger.exception("Unknown error occurred, closing connection.")
                    sock = cast(socket.socket, key.fileobj)
                    self._selector.unregister(sock)
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()

    def start(self) -> FakeLogstashService:
        self._root.listen()
        self._selector.register(self._root, selectors.EVENT_READ)
        self._selector.register(self._rshutdown, selectors.EVENT_READ)
        self._thread.start()
        return super(FakeLogstashService, self).start()

    def stop(self) -> None:
        """Stop the service

        Raises:
            RuntimeError: Failed stopping the service. Operation timed out.
        """
        if not self._thread.is_alive():
            return
        self._wshutdown.send(_CLOSE_SENTINEL)
        self._thread.join(_STOP_TIMEOUT)  # Should almost never timeout
        if self._thread.is_alive():  # pragma: no cover
            raise RuntimeError(f"Failed stopping {self.__class__.__name__}.")

        for key in self._selector.get_map().values():
            sock = cast(socket.socket, key.fileobj)
            sock.close()

        self._selector.close()

    def is_alive(self) -> bool:
        """Check if FakeLogstashService is alive.

        Returns:
            Boolean.
        """
        return self._thread.is_alive()

    def filter_records(self, level: Union[str, int]) -> Iterator[Dict[str, Any]]:
        """Filter records in the given level or above."""
        level = _level_to_int(level)

        return (record for record in self.records if logging.getLevelName(record["level"]) >= level)

    def assert_logs(self, level: Union[str, int]):
        """Asserts that log messages were received in the given level or above.

        Resembles unittest.assertLogs.

        Args:
            level: Log level by name or number

        Raises:
            AssertionError: No logs above the given level were received.
        """
        level = _level_to_int(level)

        if not any(self.filter_records(level)):
            raise AssertionError(f"No logs of level {logging.getLevelName(level)} or above were received.")

    def assert_no_logs(self, level: Union[str, int]):
        """Asserts that no log messages were received in the given level or above.

        Args:
            level: Log level by name or number

        Raises:
            AssertionError: A log above the given level was received.
        """
        level = _level_to_int(level)

        record = next(self.filter_records(level), None)
        if record:
            raise AssertionError(f"A log level {record['level']} was received. Message: {record['message']}")
