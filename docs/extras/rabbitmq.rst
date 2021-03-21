:mod:`extras.rabbit_mq` --- RabbitMQ Container Service
======================================================

.. module:: extras.rabbit_mq
    :synopsis: Running RabbitMQ server.

-------

A :class:`~service.YellowService` that runs the messaging queue
`RabbitMQ <https://www.rabbitmq.com/>`_. Uses the official docker container,
with `Pika <https://pika.readthedocs.io/en/stable/>`_ as the Python client
implementation.

.. note::

    If you wish to use this package, please install Yellowbox with the ``rabbit``
    extra. For more information, see our
    :ref:`installation guide <installation>`.


.. class:: RabbitMQService(docker_client, image="rabbitmq:latest", *,\
                           user="guest", password="guest", virtual_host="/",\
                           **kwargs)

    A :class:`~subclasses.SingleContainerService` that wraps a RabbitMQ docker
    container.

    *docker_client* is a ``docker.py`` client used to pull the RabbitMQ image
    and create the container during instance construction.

    *image* is the RabbitMQ image to use. Defaults to the latest official
    build.

    *user* and *password* are the username and password to set as the default
    credentials.

    *virtual_host* is the virtual host to use in multi-tenant system. For more
    information see the
    `appropriate documentation <https://www.rabbitmq.com/vhosts.html>`_.

    Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`~subclasses.RunMixin`.

    Has the following additional methods:

    .. method:: connection_port()

        Returns the connection port for external access.

    .. method:: connection(**kwargs)

        Returns a connected :class:`BlockingConnection\
        <pika:pika.adapters.blocking_connection.BlockingConnection>`.

        Further `kwargs` are passed to the :class:`ConnectionParameters\
        <pika:pika.connection.ConnectionParameters>` used to initialize the
        connection.

    .. method:: enable_management()

        Enables the RabbitMQ
        `Management <https://www.rabbitmq.com/management.html>`_
        plugin.

    .. method:: management_url()

        Returns the localhost RabbitMQ Management URL.

        .. note::

            Before connecting, make sure management is enabled using
            :meth:`enable_management`.

    .. method:: reset_state(force_queue_deletion=False)

        Remove all declared RabbitMQ queues.

        If *force_queue_deletion* is true, queues will be deleted regardless
        of other open consumers currently attached to the queues. Otherwise,
        removal of the queue will throw a `requests.HTTPError\
        <https://requests.readthedocs.io/en/master/api/#requests.HTTPError>`_.

    .. method:: run(docker_client, *, enable_management=False, **kwargs)

        Convenience method to run the service. Used as a context manager.

        *enable_management* automatically calls :meth:`enable_management` after
        starting the service.

        For more info about this method and it's possible keyword arguments,
        see :meth:`RunMixin.run <subclasses.RunMixin.run>`.
