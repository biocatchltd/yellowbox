from pytest import mark

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
