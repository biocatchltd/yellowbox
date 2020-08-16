from abc import ABC, abstractmethod
from typing import Dict, Union

from docker.models.containers import Container
from docker.models.networks import Network

from yellowbox.utils import LoggingIterableAdapter, get_container_ports, get_container_aliases


class YellowService(ABC):
    @abstractmethod
    def reload(self):
        pass

    @abstractmethod
    def is_alive(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @abstractmethod
    def connect(self, network: Network, **kwargs):
        pass

    @abstractmethod
    def disconnect(self, network: Network, **kwargs):
        pass


class YellowContainer(YellowService):
    def __init__(self, container: Container):
        self.container = container
        self.stdout = LoggingIterableAdapter(self.container.logs(stream=True, stdout=True, stderr=False))
        self.stderr = LoggingIterableAdapter(self.container.logs(stream=True, stdout=False, stderr=True))
        self.logs = self.container.logs(stream=True)

    def reload(self):
        self.container.reload()

    def is_alive(self):
        self.reload()
        return self.container.status.lower() not in ('exited', 'stopped')

    def kill(self, signal='SIGKILL'):
        self.container.kill(signal)

    def get_exposed_ports(self) -> Dict[int, int]:
        self.reload()
        return get_container_ports(self.container)

    def connect(self, network: Network, **kwargs):
        network.connect(self.container, **kwargs)
        self.reload()
        return get_container_aliases(self.container, network)


    def disconnect(self, network: Network, **kwargs):
        return network.disconnect(self.container, **kwargs)
