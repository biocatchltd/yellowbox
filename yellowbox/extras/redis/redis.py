from typing import ContextManager, Mapping, Optional, Sequence, Union, TypeVar, ClassVar

from redis import ConnectionError as RedisConnectionError, Redis

from yellowbox.retry import RetrySpec, Catchable
from yellowbox.extras.redis.base import BaseRedisService


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


class RedisService(BaseRedisService):

    health_exceptions: ClassVar[Catchable] = RedisConnectionError

    def health(self, retry_spec: Optional[RetrySpec] = None):
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            client.ping()

    def reset_state(self):
        client: Redis
        with self.client() as client:
            client.flushall()

    def set_state(self, db_dict: RedisState):
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            client.flushall()
            append_state(client, db_dict)

    def client(self):
        return redis_client(self)


def redis_client(service: RedisService, **kwargs) -> Redis:  # type: ignore
    port = service.client_port()
    return Redis(host='localhost', port=port, **kwargs)
