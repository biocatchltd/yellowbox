from contextlib import contextmanager
from typing import Type, TypeVar

from docker import DockerClient
from docker.models.containers import Container
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.service import SingleContainerService
from yellowbox.utils import _get_spinner, retry

REDIS_DEFAULT_PORT = 6379
_T = TypeVar("_T")


class RedisService(SingleContainerService):
    def __init__(self, container: Container, *, _auto_remove=False):
        super().__init__(container)
        self._auto_remove = _auto_remove

    def client_port(self):
        return get_ports(self.container)[REDIS_DEFAULT_PORT]

    def client(self, *, client_cls=Redis):
        port = self.client_port()
        return client_cls(host='localhost', port=port)

    def start(self):
        super().start()
        with self.client() as client:
            retry(client.ping, RedisConnectionError)
        return self

    def stop(self):
        super().stop()
        if self._auto_remove:
            self.container.remove()

    @classmethod
    def from_docker(cls, docker_client: DockerClient, image='redis:latest'):
        container = create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True)
        return cls(container, _auto_remove=True)

    @classmethod
    @contextmanager
    def run(cls: Type[_T], docker_client: DockerClient,
            image: str = 'redis:latest', spinner: bool = True) -> _T:
        spinner = _get_spinner(spinner)
        with spinner("Fetching Redis..."):
            service = cls.from_docker(docker_client, image=image)

        with spinner("Waiting for Redis to start..."):
            service.start()

        with service:
            yield service
