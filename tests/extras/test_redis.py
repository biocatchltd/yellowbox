from contextlib import closing

from docker import DockerClient
from pytest import fixture

from yellowbox.extras import YellowRedis


@fixture(scope="module")
def docker_client() -> DockerClient:
    client = DockerClient.from_env()
    client.ping()  # Make sure we're actually connected.
    with closing(client):
        yield client


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
