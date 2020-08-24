from contextlib import contextmanager
from typing import Dict, Generator, TypeVar, Union, Sequence

from docker import DockerClient
from docker.errors import ImageNotFound
from docker.models.containers import Container
from docker.models.networks import Network
from requests import HTTPError

_DEFAULT_TIMEOUT = 10

_T = TypeVar("_T")
_CT = TypeVar("_CT", bound=Container)
_Gen = Generator[_T, None, None]


def get_ports(container: Container) -> Dict[int, int]:
    """Get the exposed (published) ports of a given container

    Useful for when the ports are assigned dynamically.

    Example:
        >>> c = Container("redis:latest", publish_all_ports=True)
        >>> c.run()
        >>> c.reload()  # Must reload to get updated config.
        >>> ports = get_ports(c)
        >>> ports[6379]  # Random port assigned to 6379 inside the container
        1234

    Note: Container must be up and running. To make sure data is up-to-date,
    make sure you .reload() the container before attempting to fetch the ports.

    Args:
        container: Docker container.

    Returns:
        Port mapping {internal_container_port: external_host_port}.
    """
    # todo this probably won't work for multi-network containers
    ports = {}
    portmap = container.attrs["NetworkSettings"]["Ports"]
    for port, external_address in portmap.items():
        # Filter out unpublished ports.
        if external_address is None:
            continue

        assert len(external_address) > 0

        external_port = int(external_address[0]["HostPort"])

        port, *_ = port.partition("/")  # Strip out type (tcp, udp, ...)
        ports[int(port)] = int(external_port)

    return ports


def get_aliases(container: Container, network: Union[str, Network]) -> Sequence[str]:
    if not isinstance(network, str):
        network = network.name
    return container.attrs["NetworkSettings"]["Networks"][network]["Aliases"]


def is_alive(container: Container) -> bool:
    if is_removed(container):
        return False
    return container.status.lower() not in ('exited', 'stopped')


@contextmanager
def killing(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT,
            signal: str = 'SIGKILL') -> _Gen[_CT]:
    """A context manager that kills a docker container upon completion.

    Example:
        container = DockerContainer(...)
        with killing(container):
            ...
        # Container is now killed with SIGKILL

    Args:
        container: Container to kill upon completion
        timeout: Time to wait for container to be killed after sending a signal.
        Defaults to 10 seconds.
        signal: The signal to send to the container.

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield container
    finally:
        if is_alive(container):
            container.kill(signal)
            container.wait(timeout=timeout)


def create_and_pull(docker_client: DockerClient, image, command=None, **kwargs) -> Container:
    try:
        return docker_client.containers.create(image=image, command=command, **kwargs)
    except ImageNotFound:
        docker_client.images.pull(image, platform=None)
        return docker_client.containers.create(image=image, command=command, **kwargs)


def is_removed(container: Container):
    try:
        container.reload()
    except HTTPError:
        return True
    return False


class SafeContainerCreator:
    def __init__(self, client: DockerClient):
        self.client = client
        self.created = []

    def create_and_pull(self, image, command=None, **kwargs):
        try:
            container = create_and_pull(self.client, image, command, **kwargs)
        except Exception:
            for container in reversed(self.created):
                container.remove()
            raise
        self.created.append(container)
        return container

