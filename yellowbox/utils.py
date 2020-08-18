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
                 buffer_size: int = io.DEFAULT_BUFFER_SIZE) -> None:

        if buffer_size <= 0:
            raise ValueError("Buffer size must be greater than 0.")

        self.iterator = iter(iterable)
        self._buffer = deque()
        self.buffer_size = buffer_size
        self._current_buffer_size = 0
        self._read_lock = threading.Lock()
        self._sync_lock = threading.Lock()
        self._waiter = threading.Event()
        self._resume = threading.Event()
        self._exc = None
        self._done = False
        self.blocking = True
        self._read_thread = threading.Thread(target=self._read_loop,
                                             daemon=True)

    def _read_loop(self):
        try:
            while not self.closed:
                try:
                    data = next(self.iterator)

                    if not isinstance(data, str):
                        raise TypeError(f"Iterator should return strings, not "
                                        f"{data.__class__.__name__}.")

                except StopIteration:
                    break

                with self._sync_lock:
                    self._buffer.append(data)
                    self._current_buffer_size += len(data)
                    if self._current_buffer_size >= self.buffer_size:
                        self._resume.clear()

                self._waiter.set()
                self._resume.wait()

        except BaseException as exc:
            import traceback
            traceback.clear_frames(exc.__traceback__)
            self._exc = exc

        finally:
            self.done = True
            self._waiter.set()


    def readable(self) -> bool:
        return True

    def read(self, size: Optional[int] = None) -> str:
        if size == 0:
            return ""

        if not self.blocking and not self._buffer:
            raise BlockingIOError()

        if size is None or size < 0:
            if self.done:
                if self._exc is not None:
                    raise self._exc
                output = "".join(self._buffer)
                self._buffer.clear()
                return output

            if not self.blocking:
                raise BlockingIOError()

            while not self.done:
                self._waiter.wait()
                self._waiter.clear()
                self._resume.set()

            if self._exc is not None:
                raise self._exc

            output = "".join(self._buffer)
            self._buffer.clear()
            return output

        output = []
        if size >= self._current_buffer_size:
            try:
                item = self._buffer.popleft()
                while size > len(item):
                    size -= len(item)
                    output.append(item)
                    item = self._buffer.popleft()
            # No matter what happens here (signals etc.), we need to return the
            # buffer to a safe state
            except BaseException:
                self._current_buffer_size = sum(map(len, self._buffer))
                raise
            # Last part



