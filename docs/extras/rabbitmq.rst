:mod:`extras.rabbit_mq` --- RabbitMQ Container Service
======================================================

.. module:: extras.rabbit_mq
    :synopsis: Running RabbitMQ server.

-------

A :class:`~service.YellowService` that runs the messaging queue `RabbitMQ <https://www.rabbitmq.com/>`_. Uses the
official docker container, with `Pika <https://pika.readthedocs.io/en/stable/>`_ as the Python client implementation.

.. note::

    Requires the ``rabbit`` extra. For more information, see our :ref:`installation guide <installation>`.


.. class:: RabbitMQService(docker_client: docker.client.DockerClient, image:str ="rabbitmq:latest", *,\
                           user: str="guest", password: str="guest", virtual_host: str="/",\
                           enable_management: bool=False, container_create_kwargs: dict[str, typing.Any] | None = None,\
                           **kwargs)

    A service that runs a rabbitmq queue. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin` and :class:`~subclasses.AsyncRunMixin`.

    :param docker_client: The docker client to used to pull and create the RabbitMQ container.

    :param image: The image name to create a container of.

    :param user: The username to of the default credentials.
    :param password: The username to set as the default credentials.

    :param virtual_host: The virtual host to use in multi-tenant system. For more information see the
     `appropriate documentation <https://www.rabbitmq.com/vhosts.html>`_.
    :param enable_management: If set to true, rabbitMQ management will be automatically enabled for the service.

    :param container_create_kwargs: Additional keyword arguments passed to :meth:`docker.models.containers.ContainerCollection.create`.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: connection_port()->int

        Returns the connection port for external access from the docker host.

    .. method:: connection(**kwargs) -> pika.adapters.blocking_connection.BlockingConnection

        :param \*\*kwargs: Additional keyword arguments passed to :class:`pika.connection.ConnectionParameters` use to
         create the connection.

        Returns a connected pika connection to the rabbitMQ queue.

    .. method:: enable_management()

        Enables the RabbitMQ `Management <https://www.rabbitmq.com/management.html>`_ plugin.

        .. note::

            The RabbitMQService must be running to enable management.

    .. method:: management_url()->str

        Returns the localhost RabbitMQ Management URL.

        .. note::

            Before connecting, make sure management is enabled using :meth:`enable_management`.

    .. method:: reset_state(force_queue_deletion: bool=False)

        Remove all declared RabbitMQ queues.

        :param bool force_queue_deletion: If True, queues will be deleted regardless of other open consumers currently
         attached to the queues. Otherwise, removal of the queue will raise a `requests.HTTPError\
         <https://requests.readthedocs.io/en/master/api/#requests.HTTPError>`_.


        .. note::

            Before connecting, management must be enabled using :meth:`enable_management`.
