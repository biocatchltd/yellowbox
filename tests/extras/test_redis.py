from pytest import mark, raises
from redis import Redis

from yellowbox.extras import RedisService


@mark.parametrize('spinner', [True, False])
def test_make_redis(docker_client, spinner):
    with RedisService.run(docker_client, spinner=spinner):
        pass


def test_connection_works(docker_client):
    with RedisService.run(docker_client) as redis:
        with redis.client() as client:
            client.set('a', 12)
            assert client.get('a') == b'12'


def test_clean_slate(docker_client):
    with RedisService.run(docker_client) as redis:
        with redis.client() as client:
            with redis.clean_slate():
                client.set('a', 12)
            assert not client.keys()


def test_clean_slate_fail(docker_client):
    with RedisService.run(docker_client) as redis:
        with redis.client() as client:
            client.set('a', 12)

        with raises(RuntimeError, match='.*not empty.*'):
            with redis.clean_slate():
                pass


def test_set_state(docker_client):
    with RedisService.run(docker_client) as redis, \
            redis.clean_slate():
        redis.set_state({
            'a': 12,
            'b': {'i': 0, 'am': 2, 'hungry': 3},
            'c': [2, 3, 5, 7, 11]
        })
        client: Redis
        with redis.client() as client:
            assert client.get('a') == b'12'
            assert client.hgetall('b') == {b'i': b'0', b'am': b'2', b'hungry': b'3'}
            assert client.lrange('c', 0, -1) == [b'2', b'3', b'5', b'7', b'11']
