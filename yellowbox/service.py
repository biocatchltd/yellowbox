from abc import ABCMeta, abstractmethod
from typing import TypeVar

_T = TypeVar("_T")


class YellowService(metaclass=ABCMeta):
    @abstractmethod
    def start(self: _T) -> _T:
        """
        Start the service.

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
