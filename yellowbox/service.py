from abc import ABCMeta, abstractmethod
from contextlib import contextmanager, ExitStack
from typing import Sequence, Iterable, Mapping, Any, TypeVar, Type

from docker import DockerClient
from docker.models.containers import Container
from docker.models.networks import Network
from yellowbox.containers import is_alive, _DEFAULT_TIMEOUT, get_aliases
from yellowbox.utils import _get_spinner


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


_T = TypeVar("_T")


class ContainerService(YellowService):
    def __init__(self, containers: Sequence[Container], remove: bool, kwargs: Mapping[str, Any]):
        self.containers = containers
        self.remove = remove
        self.exit_stack = ExitStack()

    @classmethod
    @abstractmethod
    def _make_containers(cls, docker_client: DockerClient) -> Iterable[Container]:
        # must return non-started containers
        pass

    @classmethod
    def from_docker(cls, docker_client: DockerClient, remove=True, **kwargs):
        maker = cls._make_containers(docker_client, **kwargs)
        containers = []
        try:
            for container in maker:
                containers.append(container)
        except Exception:
            # remove any created containers
            for container in containers:
                container.remove()
            raise
        return cls(containers=containers, remove=remove, kwargs=kwargs)

    def start(self):
        for c in self.containers:
            c.start()
            c.reload()
        return self

    def stop(self, signal='SIGTERM'):
        self.exit_stack.close()

        for c in self.containers:
            if not is_alive(c):
                continue
            c.kill(signal)
            c.wait(timeout=_DEFAULT_TIMEOUT)
            c.reload()
            if self.remove:
                c.remove()
        return self

    def is_alive(self):
        return all(is_alive(c) for c in self.containers)

    @abstractmethod
    def _end_facing_containers(self) -> Iterable[Container]:
        pass

    def connect(self, network: Network, **kwargs) -> Sequence[str]:
        ret = None
        for efc in self._end_facing_containers():
            network.connect(efc, **kwargs)
            efc.reload()
            ret = ret or get_aliases(efc, network)
        return ret

    def disconnect(self, network: Network, **kwargs):
        for efc in self._end_facing_containers():
            network.disconnect(efc, **kwargs)
            efc.reload()

    @classmethod
    def service_name(cls):
        return cls.__name__

    @classmethod
    @contextmanager
    def run(cls: Type[_T], docker_client: DockerClient, spinner: bool = True, **kwargs) -> _T:
        spinner = _get_spinner(spinner)
        with spinner(f"Fetching {cls.service_name()} ..."):
            service = cls.from_docker(docker_client, **kwargs)

        with spinner(f"Waiting for {cls.service_name()} to start..."):
            service.start()

        with service:
            yield service


class SingleContainerService(YellowService):
    def __init__(self, container: Container):
        self.container = container

    def connect(self, network: Network):
        network.connect(self.container)
        self.container.reload()
        return get_aliases(self.container, network)

    def disconnect(self, network: Network):
        network.disconnect(self.container)
        self.container.reload()

    def is_alive(self):
        return is_alive(self.container)

    def start(self):
        self.container.start()
        self.container.reload()
        return self  # For fluent interface, i.e. "with service.start():"

    def stop(self):
        if self.is_alive():
            self.container.kill()
            self.container.wait(timeout=_DEFAULT_TIMEOUT)
            self.container.reload()
