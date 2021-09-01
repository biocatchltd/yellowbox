from yellowbox.extras.redis.base import DEFAULT_RDB_PATH, REDIS_DEFAULT_PORT, BaseRedisService

try:
    from yellowbox.extras.redis.redis import RedisService, append_state
except ImportError as exc:
    e = exc

    def RedisService():  # type: ignore[no-redef]
        raise ImportError("RedisService can not be imported without redis-py") from e

    append_state = RedisService  # type: ignore[assignment]

__all__ = ['REDIS_DEFAULT_PORT', 'DEFAULT_RDB_PATH', 'BaseRedisService', 'RedisService', 'append_state']
