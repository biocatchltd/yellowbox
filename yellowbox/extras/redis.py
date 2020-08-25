from typing import IO, Optional, TypeVar, Callable

from docker import DockerClient
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.containers import get_ports, create_and_pull, upload_file
from yellowbox.subclasses import SingleContainerService, RunnableWithContext
from yellowbox.utils import retry

REDIS_DEFAULT_PORT = 6379
DEFAULT_RDB_PATH = "/data/dump.rdb"

_T = TypeVar("_T")


class RedisService(SingleContainerService, RunnableWithContext):
    def __init__(self, docker_client: DockerClient, image='redis:latest',
                 redis_file: Optional[IO[bytes]] = None, **kwargs):
        container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
        self.started = False
        super().__init__(container, **kwargs)
        self.set_rdb(redis_file)

    def set_rdb(self, redis_file: IO[bytes]):
        if self.started:
            raise RuntimeError("Server already started. Cannot set RDB.")
        upload_file(self.container, DEFAULT_RDB_PATH, fileobj=redis_file)

    def client_port(self):
        return get_ports(self.container)[REDIS_DEFAULT_PORT]

    def client(self, *, client_cls: Callable[..., _T] = Redis) -> _T:
        port = self.client_port()
        return client_cls(host='localhost', port=port)

    def start(self):
        super().start()
        with self.client() as client:
            retry(client.ping, RedisConnectionError)
        self.started = True
        return self
