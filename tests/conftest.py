from functools import wraps
from typing import List

from docker import DockerClient
from docker.models.containers import Container
from pytest import fixture

from yellowbox import docker_client as _docker_client
from yellowbox.containers import create_and_pull as _create_and_pull


@fixture(scope="module")
def docker_client() -> DockerClient:
    with _docker_client() as client:
        yield client


@fixture
def create_and_pull():
    """A wrapper around yellowbox's create_and_pull, to ensure that all created containers are removed
    """
    created: List[Container] = []

    @wraps(_create_and_pull)
    def ret(*args, remove=True, **kwargs):
        container = _create_and_pull(*args, **kwargs)
        if remove:
            created.append(container)
        return container

    yield ret
    for c in created:
        c.remove(force=True, v=True)
