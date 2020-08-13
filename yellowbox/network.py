from typing import Union, Optional, Mapping, Any
from contextlib import contextmanager
from uuid import uuid4

from docker import DockerClient
from docker.models.containers import Container
from docker.models.networks import Network

from yellowbox.context_managers import disconnecting
from yellowbox.service import YellowService


class YellowNetwork:
    def __init__(self, network: Network):
        self.network = network

    @contextmanager
    def connect(self, container: Union[str, Container, YellowService], *,
                disconnect_kwargs: Optional[Mapping[str, Any]] = None, **connect_kwargs):
        # todo yield something?
        if disconnect_kwargs is None:
            disconnect_kwargs = {}

        if isinstance(container, YellowService):
            try:
                yield container.connect(self.network, **connect_kwargs)
            finally:
                container.disconnect(self.network, **disconnect_kwargs)
        else:
            self.network.connect(container, **connect_kwargs)
            try:
                yield
            finally:
                self.network.disconnect(container, **disconnect_kwargs)

    def disconnect(self, container, **kwargs):
        return self.network.disconnect(container, **kwargs)

    def remove(self):
        return self.network.remove()

    @classmethod
    @contextmanager
    def create(cls, docker_client: DockerClient, name=None, *args, **kwargs) -> 'YellowNetwork':
        if name is None:
            name = f"anonymous-network-{uuid4()}"
        network = docker_client.networks.create(name, *args, **kwargs)
        yellow = cls(network)
        with disconnecting(network):
            yield yellow

    @property
    def name(self):
        return self.network.name
