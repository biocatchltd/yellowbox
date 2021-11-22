from contextlib import closing, contextmanager

from docker import DockerClient


@contextmanager
def docker_client():
    """
    Starts docker client from the environment, with a fallback to default TCP port
    (for running from within virtual machines)
    """
    try:
        ret = DockerClient.from_env()
        ret.ping()
    except Exception:  # pragma: no cover
        ret = DockerClient(base_url='tcp://localhost:2375')
        ret.ping()
    with closing(ret):
        yield ret
