from abc import ABCMeta, abstractmethod
from typing import Optional, TypeVar

from yellowbox.retry import RetrySpec

_T = TypeVar("_T")


class YellowService(metaclass=ABCMeta):
    @abstractmethod
    def start(self: _T, *, retry_spec: Optional[RetrySpec] = None) -> _T:
        """
        Start the service. Wait for startup by repeatedly attempting an operation until success

        Args:
            retry_spec: The specifications for the repeated attempts. If not provided,
             a predefined default RetrySpec should be used.

        Returns:
            self, for usage as a context manager.

        """
        return self

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
