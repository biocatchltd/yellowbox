from contextlib import closing, contextmanager

from docker import DockerClient


@contextmanager
def open_docker_client():
    """
    Starts docker client from the environment, with a fallback to default TCP port
    (for running from within virtual machines)
    """
    try:
        ret = DockerClient.from_env()
        ret.ping()
    except Exception:  # noqa: BLE001
        ret = DockerClient(base_url="tcp://localhost:2375")
        ret.ping()
    with closing(ret):
        yield ret


# legacy alias
docker_client = open_docker_client
