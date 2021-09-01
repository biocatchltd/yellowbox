from yellowbox.extras.redis.base import REDIS_DEFAULT_PORT, DEFAULT_RDB_PATH, BaseRedisService

try:
    from yellowbox.extras.redis.redis import RedisService, append_state
except ImportError:
    def RedisService():
        raise ImportError("RedisService can not be imported without redis-py")

    def append_state():
        raise ImportError("append_state can not be imported without redis-py")

__all__ = ['REDIS_DEFAULT_PORT', 'DEFAULT_RDB_PATH', 'BaseRedisService', 'RedisService', 'append_state']
