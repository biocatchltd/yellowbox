from collections.abc import Callable, Mapping, Sequence
from typing import IO, Any, ContextManager, TypeVar, Union, overload

from docker import DockerClient
from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox import RunMixin
from yellowbox.containers import create_and_pull_with_defaults, get_ports, upload_file
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, SingleContainerService

__all__ = ["DEFAULT_RDB_PATH", "REDIS_DEFAULT_PORT", "RedisService", "append_state"]

from yellowbox.utils import DOCKER_EXPOSE_HOST

REDIS_DEFAULT_PORT = 6379
DEFAULT_RDB_PATH = "/data/dump.rdb"

_T = TypeVar("_T", bound=ContextManager)
RedisPrimitive = Union[str, int, float, bytes]
RedisState = Mapping[str, Union[RedisPrimitive, Mapping[Union[str, bytes], RedisPrimitive], Sequence[RedisPrimitive]]]


def append_state(client: Redis, db_state: RedisState):
    for k, v in db_state.items():
        if isinstance(v, Sequence):
            client.rpush(k, *v)
        elif isinstance(v, Mapping):
            client.hset(k, mapping=v)
        else:
            client.set(k, v)


class RedisService(SingleContainerService, RunMixin, AsyncRunMixin):
    def __init__(
        self,
        docker_client: DockerClient,
        image="redis:latest",
        redis_file: IO[bytes] | None = None,
        *,
        container_create_kwargs: dict[str, Any] | None = None,
        **kwargs,
    ):
        container = create_and_pull_with_defaults(
            docker_client, image, _kwargs=container_create_kwargs, publish_all_ports=True, detach=True
        )
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

    @overload
    def client(self, *, client_cls: Callable[..., _T], **kwargs) -> _T: ...

    @overload
    def client(self, **kwargs) -> Redis: ...

    def client(self, *, client_cls=Redis, **kwargs) -> Any:
        port = self.client_port()
        return client_cls(host=DOCKER_EXPOSE_HOST, port=port, **kwargs)

    def start(self, retry_spec: RetrySpec | None = None):
        super().start()
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            retry_spec = retry_spec or RetrySpec(attempts=15)
            retry_spec.retry(client.ping, RedisConnectionError)
        self.started = True
        return self

    async def astart(self, retry_spec: RetrySpec | None = None) -> None:
        super().start()
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            retry_spec = retry_spec or RetrySpec(attempts=15)
            await retry_spec.aretry(client.ping, RedisConnectionError)
        self.started = True

    def reset_state(self) -> None:
        client: Redis
        with self.client() as client:
            client.flushall()

    def set_state(self, db_dict: RedisState) -> None:
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            client.flushall()
            append_state(client, db_dict)
