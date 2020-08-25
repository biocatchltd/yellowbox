from pytest import mark, raises

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

        with raises(AssertionError, match='.*not empty.*'):
            with redis.clean_slate():
                pass
