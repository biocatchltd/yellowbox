from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from time import perf_counter, sleep
from typing import Optional, Callable, Type, Union, Iterable, TypeVar

_T = TypeVar('_T')


@dataclass
class RetrySpec:
    """
    Specifications for a repeated attempts af an arbitrary action that might fail.
    """

    interval: float = 2
    """
    Time between attempts in seconds.
    """
    attempts: Optional[int] = None
    """
    Max number of attempts. If None, infinite attempts are made.
    """
    timeout: Optional[float] = None
    """
    A timeout for all the attempts (including the interval) combined.
    """

    def __post_init__(self):
        if self.attempts is self.timeout is None:
            raise ValueError('RetrySpec must have either a timeout or attempts')

    def retry(self, func: Callable[[], _T],
              exceptions: Union[Type[Exception], Iterable[Type[Exception]]]) -> _T:
        """
        Retry running func until it succeeds

        Args:
            func: Function to run without arguments.
            exceptions: Single or iterable of exception types to catch. Exceptions raised by `func` not residing
            inside this iterable will be propagated.

        Returns:
            The return value of `func`'s first successful call.

        Raises:
            Any exception raised by `func` if max attempts or timeout were reached or  if the exception
            wasn't specified in exceptions list.

        """
        if self.attempts is None:
            attempt_iterator = count()
        elif self.attempts < 1:
            raise ValueError("Attempts must be greater than zero.")
        else:
            attempt_iterator = range(self.attempts - 1)

        if isinstance(exceptions, type) and issubclass(exceptions, Exception):
            exceptions = (exceptions,)

        if self.timeout:
            time_limit = perf_counter() + self.timeout
        else:
            time_limit = float('inf')

        for _ in attempt_iterator:
            try:
                return func()
            except exceptions:
                if perf_counter() > time_limit:
                    raise
            sleep(self.interval)
        return func()
