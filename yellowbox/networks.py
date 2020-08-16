from contextlib import contextmanager
from typing import Generator, TypeVar, Union
from uuid import uuid1

from docker import DockerClient
from docker.models.networks import Network
from docker.models.containers import Container

from yellowbox.service import YellowService


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
def connect(network: Network, obj: Union[Container, YellowService]):
    """Temporarily connect a container or yellow service into a network.

    Args:
        network: Docker network.
        obj: Container or YellowService to connect to the network.

    Returns:
        Context manager for handling the connection.
    """
    if isinstance(obj, YellowService):
        obj.connect(network)
    else:
        network.connect(obj)
    try:
        yield
    finally:
        if isinstance(obj, YellowService):
            obj.disconnect(network)
        else:
            network.disconnect(obj)


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
