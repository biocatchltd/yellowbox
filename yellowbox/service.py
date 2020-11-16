from abc import ABCMeta, abstractmethod
from typing import Optional

from docker.models.networks import Network

from yellowbox.retry import RetrySpec


class YellowService(metaclass=ABCMeta):
    @abstractmethod
    def start(self, *, retry_spec: Optional[RetrySpec] = None):
        """
        Start the service. Wait for startup by repeatedly attempting an operation until success

        Args:
            retry_spec: The specifications for the repeated attempts. If not provided,
             a predefined default RetrySpec should be used.

        Returns:
            self, for usage as a context manager.

        """
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def is_alive(self):
        pass

    @abstractmethod
    def connect(self, network: Network):
        pass

    @abstractmethod
    def disconnect(self, network: Network):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
