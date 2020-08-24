from abc import ABCMeta, abstractmethod

from docker.models.networks import Network


class YellowService(metaclass=ABCMeta):
    @abstractmethod
    def start(self):
        return self

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
