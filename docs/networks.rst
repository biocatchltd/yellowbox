:mod:`networks` --- Docker Network Management
=========================================================

.. module:: networks
    :synopsis: Docker Network Management

-------

.. function:: anonymous_network(client: docker.client.DockerClient, *args, **kwargs) -> docker.models.networks.Network

    Create an anonymous network with a random name.

    :param client: A docker client to use to create the network.
    :param \*args: Arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.
    :param \*\*kwargs: Keyword arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.

    :returns: A new anonymous network.

.. function:: temp_network(client: docker.client.DockerClient, name: str | None =None, *args, **kwargs) -> \
        contextlib.AbstractContextManager[docker.models.networks.Network]

    Context manager to create and remove a temporary network.

    :param client: A docker client to use to manage the network.
    :param name: The name of the network. If ``None``, a random name will be generated.
    :param \*args: Arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.
    :param \*\*kwargs: Keyword arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.

    :returns: A new temporary network.

    .. note::

        If any containers are connected to the network when the context manager is exited, they will be disconnected.

.. function:: connect(network: docker.models.networks.Network, \
        obj: docker.models.containers.Container | subclasses.ContainerService, **kwargs)\
        ->contextlib.AbstractContextManager[list[str]]

    Temporarily connect a container to a network.

    :param network: The network to connect to.
    :param obj: A container or a container service to connect to the network.
    :param \*\*kwargs: Keyword arguments to pass to the :meth:`Network.connect <docker.models.networks.Network.connect>`
        or :meth:`subclasses.ContainerService.connect` method.

    :returns: A context manager that connect and disconnects the network and the object, and yields the aliases of the
        object within the network.

.. function:: disconnecting(network: docker.models.networks.Network, *, remove: bool=False)\
        ->contextlib.AbstractContextManager[docker.models.networks.Network]

    Get a context manager that when exited, disconnects the network from all containers, and optionally deletes the
    network.

    :param network: The network to disconnect.
    :param remove: Whether to delete the network when the context manager is exited.

    :returns: A context manager that disconnects the network from all containers, and yields the network.