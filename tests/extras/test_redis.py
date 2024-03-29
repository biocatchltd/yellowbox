from pytest import fixture, mark
from redis import Redis

from tests.util import unique_name_generator
from yellowbox.extras.redis import RedisService


@mark.parametrize("spinner", [True, False])
def test_make_redis(docker_client, spinner):
    with RedisService.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_connection_works_async(docker_client):
    async with RedisService.arun(docker_client) as redis:
        with redis.client() as client:
            client.set("a", 12)
            assert client.get("a") == b"12"


@fixture(scope="module")
def redis(docker_client):
    with RedisService.run(docker_client) as service:
        yield service


key_prefix = fixture(unique_name_generator())


def test_connection_works(redis, key_prefix):
    with redis.client() as client:
        client.set(key_prefix + "a", 12)
        assert client.get(key_prefix + "a") == b"12"


def test_reset_state(redis, key_prefix):
    with redis.client() as client:
        client.set(key_prefix + "a", 12)
        redis.reset_state()
        assert not client.keys()


def test_set_state(redis, key_prefix):
    redis.set_state(
        {key_prefix + "a": 12, key_prefix + "b": {"i": 0, "am": 2, "hungry": 3}, key_prefix + "c": [2, 3, 5, 7, 11]}
    )
    client: Redis
    with redis.client() as client:
        assert client.get(key_prefix + "a") == b"12"
        assert client.hgetall(key_prefix + "b") == {b"i": b"0", b"am": b"2", b"hungry": b"3"}
        assert client.lrange(key_prefix + "c", 0, -1) == [b"2", b"3", b"5", b"7", b"11"]
