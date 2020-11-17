from abc import abstractmethod, ABC
from contextlib import contextmanager
from typing import Sequence, TypeVar, Type, Generator, Optional

from docker import DockerClient
from docker.models.containers import Container
from docker.models.networks import Network

from yellowbox.containers import is_alive, _DEFAULT_TIMEOUT, get_aliases
from yellowbox.retry import RetrySpec
from yellowbox.service import YellowService
from yellowbox.utils import _get_spinner


class ContainerService(YellowService):
    def __init__(self, containers: Sequence[Container], remove=True):
        """
        Notes:
             The containers should be ordered so that it is safe to start them in order, and to re
        """
        self.containers = containers
        self.remove = remove

    @abstractmethod
    def start(self, retry_spec: Optional[RetrySpec] = None):
        for c in self.containers:
            if c.status.lower() == 'started':
                continue
            c.start()
            c.reload()
        return self

    def stop(self, signal='SIGTERM'):
        for c in reversed(self.containers):
            if not is_alive(c):
                continue
            c.kill(signal)
            c.wait(timeout=_DEFAULT_TIMEOUT)
            c.reload()
            if self.remove:
                c.remove(v=True)

    def is_alive(self):
        return all(is_alive(c) for c in self.containers)

    @property
    def _endpoint_containers(self) -> Sequence[Container]:
        return self.containers

    def connect(self, network: Network):
        for ec in self._endpoint_containers:
            network.connect(ec)
            ec.reload()

    def disconnect(self, network: Network, **kwargs):
        for ec in reversed(self._endpoint_containers):
            network.disconnect(ec, **kwargs)
            ec.reload()


class SingleEndpointService(ContainerService):
    @property
    @abstractmethod
    def _single_endpoint(self) -> Container:
        pass

    def _endpoint_containers(self) -> Sequence[Container]:
        return self._single_endpoint,

    def connect(self, network: Network, **kwargs) -> Sequence[str]:
        network.connect(self._single_endpoint, **kwargs)
        self._single_endpoint.reload()
        return get_aliases(self._single_endpoint, network)

    def disconnect(self, network: Network, **kwargs):
        network.disconnect(self._single_endpoint, **kwargs)
        self._single_endpoint.reload()


class SingleContainerService(SingleEndpointService, ABC):
    def __init__(self, container: Container, **kwargs):
        super().__init__((container,), **kwargs)

    @property
    def container(self):
        return self.containers[0]

    @property
    def _single_endpoint(self) -> Container:
        return self.container


_T = TypeVar("_T")


class RunMixin:
    @classmethod
    def service_name(cls):
        return cls.__name__

    @classmethod
    @contextmanager
    def run(cls: Type[_T], docker_client: DockerClient, *, spinner: bool = True,
            retry_spec: Optional[RetrySpec] = None, **kwargs) -> Generator[_T, None, None]:
        """
        Same as RunMixin.run, but allows to forward retry arguments to the blocking start method.

        Args:
            docker_client: a DockerClient instance to use when creating the service
            spinner: whether or not to use a yaspin spinner
            retry_spec: forwarded to cls.start
            **kwargs: all keyword arguments are forwarded to the class's constructor
        """
        spinner = _get_spinner(spinner)
        with spinner(f"Fetching {cls.service_name()} ..."):
            service = cls(docker_client, **kwargs)

        with spinner(f"Waiting for {cls.service_name()} to start..."):
            service.start(retry_spec=retry_spec)

        with service:
            yield service
