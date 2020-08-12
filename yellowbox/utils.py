import json
from collections import deque
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import suppress
from time import sleep
from typing import Callable, TypeVar, Union, Iterable, Dict, Any, Deque, Iterator

from docker.models.containers import Container

_T = TypeVar('_T')
_ExcType = TypeVar('_ExcType', bound=Exception)


def retry(func: Callable[[], _T],
          exceptions: Union[_ExcType, Iterable[_ExcType]] = (Exception,), *,
          interval: float = 2, attempts: int = 10) -> _T:
    """Retry running func until it no longer raises the given exceptions

    Args:
        func: Function to run with no arguments.
        exceptions: Single or iterable of exception types to catch.
        Defaults to <Exception>. Exceptions raised by `func` not residing
        inside this iterable will be propagated.
        interval: Time between tries in seconds. Defaults to 2.
        attempts: Max number of attempts. Defaults to 10.

    Returns:
        Result of `func` once it ran successfully.

    Raises:
        Any exception raised by `func` if max attempts were reached or exception
        wasn't specified in exceptions list.
    """
    if not isinstance(attempts, int):
        raise TypeError("Attempts must be an integer.")

    if attempts < 1:
        raise ValueError("Attempts must be greater than zero.")

    if isinstance(exceptions, type) and issubclass(exceptions, Exception):
        exceptions = (exceptions,)

    # Last attempt is outside loop
    attempts -= 1

    while attempts:
        with suppress(*exceptions):
            return func()
        sleep(interval)

    return func()


class LoggingIterableAdapter(Iterable[Dict[str, Any]]):
    """An adapter to convert blocking docker logs to non-blocking message streams, not thread-safe
    """

    # if the iterator takes more than this amount of time, we're gonna say there's no log messages to read
    nonblocking_timeout = 0.1

    def __init__(self, source: Iterator[bytes]):
        self.source = source
        self.pending: Deque[Dict[str, Any]] = deque()
        self.executor = ThreadPoolExecutor(1)
        self.done = False

    def _load(self):
        if self.done:
            raise StopIteration
        try:
            message_bundle = next(self.source)
        except StopIteration:
            self.done = True
            raise
        else:
            messages = str(message_bundle, 'utf-8').splitlines()
            self.pending.extend(
                json.loads(msg) for msg in messages
            )

    def read(self):
        if not self.pending:
            self._load()
        return self.pending.popleft()

    def read_nonblocking(self):
        if self.pending:
            return self.pending.popleft()
        self.executor.submit(self._load)
        sleep(self.nonblocking_timeout)
        if self.done:
            raise StopIteration
        if not self.pending:
            return None
        return self.pending.popleft()

    def __iter__(self):
        return self

    def __next__(self):
        return self.read()


def get_container_ports(container: Container) -> Dict[int, int]:
    # todo this probably won't work for multi-network containers
    """Get the exposed (published) ports of a given container

    Useful for when the ports are assigned dynamically.

    Example:
        >>> c = Container("redis:latest", publish_all_ports=True)
        >>> c.run()
        >>> c.reload()  # Must reload to get updated config.
        >>> ports = get_container_ports(c)
        >>> ports[6379]  # Random port assigned to 6379 inside the container
        1234

    Note: Container must be up and running. To make sure data is up-to-date,
    make sure you .reload() the container before attempting to fetch the ports.

    Args:
        container: Docker container.

    Returns:
        Port mapping {internal_container_port: external_host_port}.
    """
    ports = {}
    portmap = container.attrs["NetworkSettings"]["Ports"]
    for port, external_address in portmap.items():
        # Filter out unpublished ports.
        if external_address is None:
            continue

        assert len(external_address) > 0

        external_port = int(external_address[0]["HostPort"])

        port, *_ = port.partition("/")  # Strip out type (tcp, udp, ...)
        ports[int(port)] = int(external_port)

    return ports
