from typing import TypeVar, Iterable

from docker import DockerClient
from docker.models.containers import Container
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.service import ContainerService
from yellowbox.utils import retry

REDIS_DEFAULT_PORT = 6379
_T = TypeVar("_T")


class RedisService(ContainerService):
    @property
    def container(self):
        return next(iter(self.containers))

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

    @classmethod
    def _make_containers(cls, docker_client: DockerClient, image='redis:latest') -> Iterable[Container]:
        yield create_and_pull(docker_client, image, publish_all_ports=True, detach=True)

    def _endpoint_containers(self) -> Iterable[Container]:
        return self.containers
