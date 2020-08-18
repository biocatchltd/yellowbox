from contextlib import closing
import platform

from docker import DockerClient
from pytest import fixture


@fixture(scope="module")
def docker_client() -> DockerClient:
    client = DockerClient.from_env()
    client.ping()  # Make sure we're actually connected.
    with closing(client):
        yield client


@fixture
def host_ip():
    if platform.system() == "Linux":
        return '172.17.0.1'
    else:
        return 'host.docker.internal'
