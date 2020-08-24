from typing import TypeVar, Callable

from docker import DockerClient
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.subclasses import SingleContainerService, RunnableWithContext
from yellowbox.utils import retry

REDIS_DEFAULT_PORT = 6379
_T = TypeVar("_T")


class RedisService(SingleContainerService, RunnableWithContext):
    def client_port(self):
        return get_ports(self.container)[REDIS_DEFAULT_PORT]

    def client(self, *, client_cls: Callable[..., _T] = Redis) -> _T:
        port = self.client_port()
        return client_cls(host='localhost', port=port)

    def start(self):
        super().start()
        with self.client() as client:
            retry(client.ping, RedisConnectionError)
        return self

    def __init__(self, docker_client: DockerClient, image='redis:latest'):
        super().__init__(
            create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
        )
