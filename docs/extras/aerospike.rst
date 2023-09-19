:mod:`extras.aerospike` --- Aerospike Database Service
============================================================

.. module:: extras.aerospike
    :synopsis: Serving Aerospike database.

-------

A :class:`~service.YellowService` for running Aerospike DB. Runs the official Aerospike docker image.

.. note::

    Requires the ``aerospike`` extra. For more information, see our :ref:`installation guide <installation>`.

.. class:: AerospikeService(docker_client: docker.client.DockerClient, image='aerospike:ce-5.7.0.8', *, \
    container_create_kwargs: dict[str, typing.Any] | None = None, **kwargs)

    A service to run the aerospike database. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin` and :class:`~subclasses.AsyncRunMixin`.

    :param docker_client: The docker client to used to pull and create the container.

    :param image: The image name to create a container of.

    :param container_create_kwargs: Additional keyword arguments passed to :meth:`docker.models.containers.ContainerCollection.create`.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: client(config=...)->typing.ContextManager[aerospike.Client]

        Returns context manager to  a connected aerospike client.

        :param config: if provided, additional configuration to set to the client (not including the "hosts" config)
    
    .. method:: client_port() -> int

        Returns the port to be used when connecting to the Redis server from the docker host.

    .. attribute:: namespace

        The namespace of the database