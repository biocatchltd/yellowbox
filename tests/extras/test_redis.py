from yellowbox.extras import YellowRedis


def test_make_redis(docker_client):
    with YellowRedis.run(docker_client):
        pass


def test_make_redis_no_spinner(docker_client):
    with YellowRedis.run(docker_client, spinner=False):
        pass


def test_connection_works(docker_client):
    with YellowRedis.run(docker_client) as redis:
        with redis.client() as client:
            client.set('a', 12)
            assert client.get('a') == b'12'
