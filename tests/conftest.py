from contextlib import closing
import platform
from functools import wraps
from typing import List

from docker import DockerClient
from docker.models.containers import Container
from pytest import fixture

from yellowbox.containers import create_and_pull as _create_and_pull


@fixture(scope="module")
def docker_client() -> DockerClient:
    try:
        ret = DockerClient.from_env()
        ret.ping()
    except Exception:
        ret = DockerClient(base_url='tcp://localhost:2375')
        ret.ping()

    try:
        yield ret
    finally:
        ret.close()


@fixture
def host_ip():
    if platform.system() == "Linux" and ('Microsoft' not in platform.uname().release):
        return '172.17.0.1'
    else:
        return 'host.docker.internal'


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
