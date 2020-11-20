import json
import threading
from typing import Optional, cast

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

LOGSTASH_DEFAULT_PORT = 5959



class LogstashService(YellowService):
    split_token = b"\n"
    encoding = "utf-8"

    def __init__(self):
        self.records = []
        sock = socket.socket()
        sock.bind(("0.0.0.0", 0))
        self._root = sock
        _background = WeakMethod(self._background_thread)
        self._thread = threading.Thread(target=lambda: _background()())
        self._selector = selectors.DefaultSelector()
        self._rclose, self._wclose = socket.socketpair()

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
        partial_part = b""

        def callback():
            nonlocal partial_part

            data = sock.recv(1024)
            if not data:
                self._selector.unregister(sock)
                return

            parts = data.split(self.split_token)
            if len(parts) == 1:
                partial_part += parts[0]
                return

            parts[0] = partial_part + parts[0]
            partial_part = parts.pop()

            for part in parts:
                record_dict = json.loads(part.decode(self.encoding))
                self.records.append(record_dict)

        return callback

    def _background_thread(self):
        while True:
            events = self._selector.select(timeout=5)  # For signal handling
            for key, mask in events:

                # Handle closing request
                if key.fileobj is self._wclose:
                    for sock in self._selector.get_map():
                        sock = cast(socket.socket, sock)
                        sock.close()
                    self._selector.close()
                    return

                # Handle new connection
                if key.fileobj is self._root:
                    new_socket, _ = self._root.accept()
                    self._selector.register(new_socket, selectors.EVENT_READ,
                                            self._create_callback(new_socket))
                    continue

                # Run callback
                key.data()

    def start(self, *, retry_spec: Optional[RetrySpec] = None):
        self._thread.start()
        super(LogstashService, self).start(retry_spec=retry_spec)

    def stop(self):
        self._rclose.send(b"\0")
        self._thread.join(5)  # Should almost never timeout
        if self._thread.is_alive():
            raise RuntimeError(f"Failed stopping {self.__class__.__name__}.")

    def connect(self, network):
        # since the logstash service is not docker related, it cannot actually connect to the network. However,
        # other containers, connected to the network or not, can connect to the service with docker's usual host
        return [_docker_host_name]

    def disconnect(self, network):
        pass

