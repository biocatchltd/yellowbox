from typing import ContextManager, Mapping, Optional, Sequence, Union, TypeVar

from redis import ConnectionError as RedisConnectionError, Redis
from redis.client import Redis as Redis_Client

from yellowbox.retry import RetrySpec
from yellowbox.extras.redis.base import BaseRedisService


RedisPrimitive = Union[str, int, float, bytes]
RedisState = Mapping[str, Union[RedisPrimitive, Mapping[str, RedisPrimitive], Sequence[RedisPrimitive]]]

_T = TypeVar("_T", bound=ContextManager)


def append_state(client: Redis, db_state: RedisState):
    for k, v in db_state.items():
        if isinstance(v, Sequence):
            client.rpush(k, *v)
        elif isinstance(v, Mapping):
            client.hset(k, mapping=v)  # type: ignore
        else:
            client.set(k, v)


class RedisService(BaseRedisService):

    def health(self, retry_spec: Optional[RetrySpec] = None):
        client_cm: ContextManager[Redis] = self.client()
        with client_cm as client:
            retry_spec = retry_spec or RetrySpec(attempts=10)
            retry_spec.retry(client.ping, RedisConnectionError)

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


def redis_client(service: RedisService, **kwargs) -> _T:  # type: ignore
    port = service.client_port()
    return Redis_Client(host='localhost', port=port, **kwargs)
