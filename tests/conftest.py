from contextlib import closing

from docker import DockerClient
from pytest import fixture


@fixture(scope="module")
def docker_client() -> DockerClient:
    client = DockerClient.from_env()
    client.ping()  # Make sure we're actually connected.
    with closing(client):
        yield client