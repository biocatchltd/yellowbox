import json
import logging
import threading
from typing import Optional, Union, cast

from docker import DockerClient
from yellowbox.utils import _docker_host_name
import socket
import threading
import selectors

from yellowbox.retry import RetrySpec
from weakref import WeakMethod
from yellowbox.containers import get_ports, create_and_pull
from yellowbox.subclasses import SingleContainerService, RunMixin, YellowService

__all__ = ['LogstashService', 'LOGSTASH_DEFAULT_PORT']
_logger = logging.getLogger(__name__)

LOGSTASH_DEFAULT_PORT = 5959

_CLOSE_SENTINEL = b"\0"
_LISTEN_BACKLOG = 5
_STOP_TIMEOUT = 5


class LogstashService(YellowService):
    split_token = b"\n"
    encoding = "utf-8"

    def __init__(self):
        self.records = []
        sock = socket.socket()
        sock.bind(("0.0.0.0", 0))
        self._root = sock
        _background = WeakMethod(self._background_thread)
        self._thread = threading.Thread(target=lambda: _background()(),
                                        daemon=True)
        self._selector = selectors.DefaultSelector()
        self._rclose, self._wclose = socket.socketpair()
        self.port = self._root.getsockname()[1]

    def __del__(self):
        # Will never happen while thread is running.
        try:
            # Order is important.
            self._root.close()
            self._selector.close()
            self._rclose.close()
            self._wclose.close()
        except AttributeError:
            pass

    def _create_callback(self, sock):
        partial_parts = []
        split_token = self.split_token
        encoding = self.encoding

        def process_socket_data():
            data = sock.recv(1024)
            if not data:
                self._selector.unregister(sock)
                return

            parts = data.split(split_token)

            # Single partial part (no token)
            if len(parts) == 1:
                partial_parts.append(parts[0])
                return

            partial_parts.append(parts[0])
            parts[0] = b"".join(partial_parts)
            partial_parts[:] = parts.pop()

            try:
                for part in parts:
                    record_dict = json.loads(part.decode(encoding))
                    self.records.append(record_dict)
            except json.JSONDecodeError:
                self._selector.unregister(sock)
                sock.close()
                # noinspection PyUnboundLocalVariable
                _logger.exception("Failed decoding json, closing socket. "
                                  "Data received: %s", part)
                return

        return process_socket_data

    def _background_thread(self):
        while True:
            events = self._selector.select(timeout=5)  # For signal handling
            for key, mask in events:
                # Handle closing request
                if key.fileobj is self._rclose:
                    assert self._rclose.recv(
                        len(_CLOSE_SENTINEL)) == _CLOSE_SENTINEL
                    return

                # Handle new connection
                if key.fileobj is self._root:
                    new_socket, _ = self._root.accept()
                    self._selector.register(new_socket, selectors.EVENT_READ,
                                            self._create_callback(new_socket))
                    continue

                # Run callback
                try:
                    key.data()
                except Exception:
                    _logger.exception("Unknown error occurred, closing connection.")
                    self._selector.unregister(key.fileobj)
                    # noinspection PyUnresolvedReferences
                    key.fileobj.close()

    def start(self, *, retry_spec: Optional[RetrySpec] = None):
        self._root.listen(_LISTEN_BACKLOG)
        self._selector.register(self._root, selectors.EVENT_READ)
        self._selector.register(self._rclose, selectors.EVENT_READ)
        self._thread.start()
        super(LogstashService, self).start(retry_spec=retry_spec)

    def stop(self):
        if not self._thread.is_alive():
            return
        self._wclose.send(_CLOSE_SENTINEL)
        self._thread.join(_STOP_TIMEOUT)  # Should almost never timeout
        if self._thread.is_alive():
            raise RuntimeError(f"Failed stopping {self.__class__.__name__}.")

        for key in self._selector.get_map().values():
            sock = cast(socket.socket, key.fileobj)
            sock.close()

        self._selector.close()

    def is_alive(self):
        return self._thread.is_alive()

    def connect(self, network):
        # since the logstash service is not docker related, it cannot actually connect to the network. However,
        # other containers, connected to the network or not, can connect to the service with docker's usual host
        return [_docker_host_name]

    def disconnect(self, network):
        pass

    def _filter_records(self, level: int):
        return (record for record in self.records if
                logging.getLevelName(record["level"]) >= level)

    def assert_logs(self, level: Union[str, int]):
        """Asserts that log messages were received in the given level or above.

        Resembles unittest.assertLogs.

        Args:
            level: Log level by name or number

        Raises:
            AssertionError: No logs above the given level were received.
        """
        if not isinstance(level, int):
            level = logging.getLevelName(level.upper())

        # In rare cases it might be false, but shouldn't happen generally.
        assert isinstance(level, int)

        if not any(self._filter_records(level)):
            raise AssertionError(f"No logs of level {logging.getLevelName(level)} "
                                 f"or above were received.")

    def assert_no_logs(self, level: Union[str, int]):
        """Asserts that no log messages were received in the given level or above.

         Args:
             level: Log level by name or number

         Raises:
             AssertionError: A log above the given level was received.
         """
        if not isinstance(level, int):
            level = logging.getLevelName(level.upper())

        # In rare cases it might be false, but shouldn't happen generally.
        assert isinstance(level, int)

        record = next(self._filter_records(level), None)
        if record:
            raise AssertionError(f"A log level {record['level']} was received. "
                                 f"Message: {record['message']}")
