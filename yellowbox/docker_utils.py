from contextlib import contextmanager

from docker import DockerClient


@contextmanager
def docker_client():
    """
    Starts docker client, while being WSL-aware
    """
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
