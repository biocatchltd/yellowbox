from typing import IO, Callable, ContextManager, Mapping, Optional, Sequence, TypeVar, Union

from docker import DockerClient
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox import RunMixin
from yellowbox.containers import create_and_pull, get_ports, upload_file
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import SingleContainerService

__all__ = ['RedisService', 'REDIS_DEFAULT_PORT', 'DEFAULT_RDB_PATH', 'append_state']

REDIS_DEFAULT_PORT = 6379
DEFAULT_RDB_PATH = "/data/dump.rdb"

_T = TypeVar("_T", bound=ContextManager)
RedisPrimitive = Union[str, int, float, bytes]
RedisState = Mapping[str, Union[RedisPrimitive, Mapping[str, RedisPrimitive], Sequence[RedisPrimitive]]]


def append_state(client: Redis, db_state: RedisState):
    for k, v in db_state.items():
        if isinstance(v, Sequence):
            client.rpush(k, *v)
        elif isinstance(v, Mapping):
            client.hset(k, mapping=v)  # type: ignore
        else:
            client.set(k, v)


class RedisService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='redis:latest',
                 redis_file: Optional[IO[bytes]] = None, **kwargs):
        container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
        self.started = False
        super().__init__(container, **kwargs)

        if redis_file:
            self.set_rdb(redis_file)

    def set_rdb(self, redis_file: IO[bytes]):
        if self.started:
            raise RuntimeError("Server already started. Cannot set RDB.")
        upload_file(self.container, DEFAULT_RDB_PATH, fileobj=redis_file)

    def client_port(self):
        return get_ports(self.container)[REDIS_DEFAULT_PORT]

    def client(self, *, client_cls: Callable[..., _T] = Redis, **kwargs) -> _T:  # type: ignore
        port = self.client_port()
        return client_cls(host='localhost', port=port, **kwargs)

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            retry_spec = retry_spec or RetrySpec(attempts=10)
            retry_spec.retry(client.ping, RedisConnectionError)
        self.started = True
        return self

    def reset_state(self):
        client: Redis
        with self.client() as client:
            client.flushall()

    def set_state(self, db_dict: RedisState):
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            client.flushall()
            append_state(client, db_dict)
