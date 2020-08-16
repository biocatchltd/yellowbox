from contextlib import contextmanager
from typing import Generator, TypeVar
from uuid import uuid1

from docker import DockerClient
from docker.models.networks import Network

_T = TypeVar("_T")
_NT = TypeVar("_NT", bound=Network)
_Gen = Generator[_T, None, None]


@contextmanager
def temp_network(client: DockerClient, name=None, *args, **kwargs):
    """Context manager for creating a temporary Docker network

    Network will be automatically removed upon context manager completion.

    Example:
        >>> client = docker.from_env()
        >>> with temp_network(client) as network:
        ...  print(network.name)
        ...
        yellowbox-...

    Args:
        client: Docker client to create network with.
        name: Network name. Defaults to a randomly generated name, with the
        prefix "yellowbox".
        *args, **kwargs: Extra arguments for docker network creation.

    Returns:
        Context manager for the newly created network
    """
    name = name or f"yellowbox-{uuid1()}"
    with disconnecting(client.networks.create(name, *args, **kwargs),
                       remove=True) as network:
        yield network


@contextmanager
def disconnecting(network: _NT, *, remove: bool = False) -> _Gen[_NT]:
    """A context manager that disconnects a docker network upon completion.

    Example:
        network = DockerNetwork(...)
        with disconnecting(network):
            ...
        # Network is now disconnected from all containers.

    Args:
        network: Network to disconnect upon completion.
        remove: Whether to remove the network upon completion or not.

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield network
    finally:
        for container in network.containers:
            network.disconnect(container)
        if remove:
            network.remove()
