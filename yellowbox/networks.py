from contextlib import contextmanager
from typing import Generator, TypeVar, Union
from uuid import uuid1

from docker import DockerClient
from docker.models.networks import Network
from docker.models.containers import Container

from yellowbox.containers import get_aliases, is_removed
from yellowbox.service import YellowService

__all__ = ['temp_network', 'anonymous_network', 'connect', 'disconnecting']

_T = TypeVar("_T")
_NT = TypeVar("_NT", bound=Network)


def anonymous_network(client: DockerClient, *args, **kwargs) -> Network:
    name = f"yellowbox-{uuid1()}"
    return client.networks.create(name, *args, **kwargs)


@contextmanager
def temp_network(client: DockerClient, name=None, *args, **kwargs):
    """Context manager for creating a temporary Docker network

    Network will be automatically removed upon context manager completion.

    Example:
        >>> client = DockerClient.from_env()
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
    if name:
        network = client.networks.create(name, *args, **kwargs)
    else:
        network = anonymous_network(client, *args, **kwargs)
    with disconnecting(network, remove=True) as network:
        yield network


@contextmanager
def connect(network: Network, obj: Union[Container, YellowService], **kwargs):
    """Temporarily connect a container or yellow service into a network.

    Args:
        network: Docker network.
        obj: Container or YellowService to connect to the network.

    Returns:
        Context manager for handling the connection.
    """
    if isinstance(obj, YellowService):
        ret = obj.connect(network, **kwargs)
    else:
        network.connect(obj, **kwargs)
        obj.reload()
        ret = get_aliases(obj, network)
    try:
        yield ret
    finally:
        if isinstance(obj, YellowService):
            obj.disconnect(network)
        elif not is_removed(obj):
            network.disconnect(obj)


@contextmanager
def disconnecting(network: _NT, *, remove: bool = False) -> Generator[_NT, None, None]:
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
