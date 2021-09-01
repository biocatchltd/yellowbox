from abc import abstractmethod
from typing import IO, Optional

from docker import DockerClient

from yellowbox import RunMixin
from yellowbox.containers import create_and_pull, get_ports, upload_file
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import SingleContainerService


REDIS_DEFAULT_PORT = 6379
DEFAULT_RDB_PATH = "/data/dump.rdb"


class BaseRedisService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='redis:latest',
                 redis_file: Optional[IO[bytes]] = None, **kwargs):
        container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
        self.started = False
        super().__init__(container, **kwargs)

        if redis_file:
            self.set_rdb(redis_file)

    @abstractmethod
    def health(self):
        pass

    def set_rdb(self, redis_file: IO[bytes]):
        if self.started:
            raise RuntimeError("Server already started. Cannot set RDB.")
        upload_file(self.container, DEFAULT_RDB_PATH, fileobj=redis_file)

    def client_port(self):
        return get_ports(self.container)[REDIS_DEFAULT_PORT]

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()
        self.health()
        self.started = True
        return self
