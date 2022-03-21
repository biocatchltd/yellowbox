from docker import DockerClient
from pytest import fixture

from yellowbox.clients import open_docker_client


@fixture(scope="session")
def docker_client() -> DockerClient:
    with open_docker_client() as client:
        yield client
