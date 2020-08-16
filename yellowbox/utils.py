import io
import json
import threading
from collections import deque
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager, nullcontext, suppress
from time import sleep
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, Optional, TypeVar, Union

from yaspin import yaspin

_T = TypeVar('_T')
_ExcType = TypeVar('_ExcType', bound=Exception)
_SPINNER_FAILMSG = "💥 "
_SPINNER_SUCCESSMSG = "✅ "


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
    for _ in range(attempts - 1):
        with suppress(*exceptions):
            return func()
        sleep(interval)
        attempts -= 1

    return func()


@contextmanager
def _spinner(text):
    with yaspin(text=text) as spinner:
        try:
            yield
        except Exception:
            spinner.fail(_SPINNER_FAILMSG)
            raise
        spinner.ok(_SPINNER_SUCCESSMSG)


def _get_spinner(fake=False) -> Callable[[str], AbstractContextManager]:
    if fake:
        return lambda text: nullcontext()
    return _spinner


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


# TODO: complete
class _IterableIO(io.TextIOBase):
    def __init__(self, iterable: Iterable[str],
                 buffer_size=io.DEFAULT_BUFFER_SIZE) -> None:
        self.iterator = iter(iterable)
        self._buffer = deque()
        self.buffer_size = buffer_size
        self._current_buffer_size = 0
        self._waiter = threading.Event()
        self._done = False
        self.blocking = True
        self._read_thread = threading.Thread(target=self._read_loop)

    def _read_loop(self):
        while not self.closed:
            pass

    def setblocking(self, mode: bool) -> None:
        self.blocking = False

    def readable(self) -> bool:
        return True

    def read(self, size: Optional[int] = None) -> str:
        if size == 0:
            return ""

        if not self.blocking and not self._buffer:
            exc = BlockingIOError()
            exc.characters_written = 0
            raise exc

        if size is None or size < 0:
            pass
