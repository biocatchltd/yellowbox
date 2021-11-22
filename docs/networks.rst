:mod:`networks` --- Docker Network Management
=========================================================

.. module:: networks
    :synopsis: Docker Network Management

-------

.. function:: anonymous_network(client, *args, **kwargs)

    Create an anonymous network with a random name.

    :param client: A :class:`~docker.Client.DockerClient` to use to create the network.
    :param \*args: Arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.
    :param \*\*kwargs: Keyword arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.

    :returns: A new anonymous network.
    :rtype: :class:`docker.models.networks.Network`

.. function:: temp_network(client, name=None, *args, **kwargs)

    Context manager to create and remove a temporary network.

    :param client: A :class:`~docker.Client.DockerClient` to use to manage the network.
    :param name: The name of the network. If ``None``, a random name will be generated.
    :param \*args: Arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.
    :param \*\*kwargs: Keyword arguments to pass to the
        :meth:`NetworkCollection.create <docker.models.networks.NetworkCollection.create>` method.

    :returns: A new temporary network.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`docker.models.networks.Network`\]

    .. note::

        If any containers are connected to the network when the context manager is exited, they will be disconnected.

.. function:: connect(network, obj, **kwargs)

    Temporarily connect a container to a network.

    :param network: The network to connect to.
    :type network: :class:`~docker.models.networks.Network`
    :param obj: A container or a container service to connect to the network.
    :type obj: :class:`~docker.models.containers.Container` | :class:`~subclasses.ContainerService`
    :param \*\*kwargs: Keyword arguments to pass to the :meth:`Network.connect <docker.models.networks.Network.connect>`
        or :meth:`subclasses.ContainerService.connect` method.

    :returns: A context manager that connect and disconnects the network and the object, and yields the aliases of the
        object within the network.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[\
     :class:`list`\[:class:`str`\]\]

.. function:: disconnecting(network, *, remove=False)

    Get a context manager that when exited, disconnects the network from all containers, and optionally deletes the
    network.

    :param network: The network to disconnect.
    :type network: :class:`~docker.models.networks.Network`
    :param bool remove: Whether to delete the network when the context manager is exited.

    :returns: A context manager that disconnects the network from all containers, and yields the network.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`~docker.models.networks.Network`\]