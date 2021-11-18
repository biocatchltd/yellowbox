:mod:`extras.kafka` --- Redis Database Service
==============================================

.. module:: extras.kafka
    :synopsis: Apache Kafka Queue.

-------

A :class:`~service.YellowService` for running an Apache Kafka Queue. Runs the Bitnami Kafka and Zookeeper
docker images.

.. note::

    Requires the ``kafka`` extra. For more information, see our :ref:`installation guide <installation>`.

.. class:: KafkaService(docker_client, tag_or_images = 'latest', inner_port=0, outer_port=0, **kwargs)

    A service to run the redis database. Inherits from :class:`~subclasses.SingleEndpointService`. Usable with
    :class:`~subclasses.RunMixin`.

    :param docker_client: The docker client to used to pull and create the Postgresql container.
    :type docker_client: :class:`docker.DockerClient<docker.client.DockerClient>`

    :param tag_or_images: The images to use to run the Kafka queue. If a string, it is used as the tag for both the
        bitnami zookeeper and kafka broker images. If a tuple, it is used as the image name for the zookeeper and broker
        , respectively.
    :type tag_or_images: str | (str, str)

    :param int inner_port: The internal port to expose on the Kafka broker for the zookeeper. Default is 0, which
        will assign to a random unoccupied port.

    :param int outer_port: The external port to expose on the Kafka broker for consumers and producers. Default is 0,
        which will assign to a random unoccupied port.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleEndpointService`.

    Has the following additional methods:

    .. method:: connection_port()

        Returns the outer port the Kafka broker is listening on.

    .. method:: consumer() -> typing.ContextManager[kafka.KafkaConsumer]

        Creates a kafka consumer for the service and wraps it in a closing context manager.

    .. method:: producer() -> typing.ContextManager[kafka.KafkaProducer]

        Creates a kafka producer for the service and wraps it in a closing context manager.
