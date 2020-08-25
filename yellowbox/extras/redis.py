from contextlib import contextmanager
from typing import TypeVar, Callable, Mapping, Union, Sequence

from docker import DockerClient
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.subclasses import SingleContainerService, RunMixin
from yellowbox.utils import retry

REDIS_DEFAULT_PORT = 6379
_T = TypeVar("_T")
RedisPrimitive = Union[str, int, float, bytes]
RedisState = Mapping[str, Union[RedisPrimitive, Mapping[str, RedisPrimitive], Sequence[RedisPrimitive]]]


def append_state(client: Redis, db_state: RedisState):
    for k, v in db_state.items():
        if isinstance(v, Sequence):
            client.rpush(k, *v)
        elif isinstance(v, Mapping):
            client.hset(k, mapping=v)
        else:
            client.set(k, v)


class RedisService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='redis:latest', **kwargs):
        super().__init__(
            create_and_pull(docker_client, image, publish_all_ports=True, detach=True),
            **kwargs
        )

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

    @contextmanager
    def clean_slate(self):
        client: Redis
        with self.client() as client:
            keys = client.keys()
            if keys:
                raise RuntimeError(f'Redis db is not empty (found keys {keys})')
            yield
            client.flushall()

    def set_state(self, db_dict: RedisState):
        client: Redis
        with self.client() as client:
            client.flushall()
            append_state(client, db_dict)
