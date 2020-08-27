from contextlib import AbstractContextManager, contextmanager, nullcontext, suppress
from time import sleep
from typing import Callable, Iterable, TypeVar, Union, Type

from yaspin import yaspin

_T = TypeVar('_T')
_SPINNER_FAILMSG = "💥 "
_SPINNER_SUCCESSMSG = "✅ "


def retry(func: Callable[[], _T],
          exceptions: Union[Type[Exception], Iterable[Type[Exception]]] = (Exception,), *,
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


def _get_spinner(real=True) -> Callable[[str], AbstractContextManager]:
    if not real:
        return lambda text: nullcontext()
    return _spinner
