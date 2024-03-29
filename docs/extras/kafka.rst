:mod:`extras.kafka` --- Apache Kafka Queue
==============================================

.. module:: extras.kafka
    :synopsis: Apache Kafka Queue.

-------

A :class:`~service.YellowService` for running an Apache Kafka Queue. Runs the Bitnami Kafka and Zookeeper
docker images.

.. note::

    Requires the ``kafka`` extra. For more information, see our :ref:`installation guide <installation>`.

.. note::

    This service runs a kafka broker/zookeeper pair. For a lightweight kraft service, see `the yellowbox-kraft library <https://github.com/biocatchltd/yellowbox-kraft>`_.

.. class:: KafkaService(docker_client: docker.client.DockerClient, tag_or_images : str | tuple[str, str] = 'latest', inner_port : int=0, outer_port: int=0, bitnami_debug = False, **kwargs)

    A service to run the kafka queue. Inherits from :class:`~subclasses.SingleEndpointService`. Usable with
    :class:`~subclasses.RunMixin` and :class:`~subclasses.AsyncRunMixin`.

    :param docker_client: The docker client to used to pull and create the Kafka containers.

    :param tag_or_images: The images to use to run the Kafka queue. If a string, it is used as the tag for both the
        bitnami zookeeper and kafka broker images. If a tuple, it is used as the image name for the zookeeper and broker
        , respectively.

    :param inner_port: The internal port to expose on the Kafka broker for the zookeeper. Default is 0, which
        will assign to a random unoccupied port.

    :param outer_port: The external port to expose on the Kafka broker for consumers and producers. Default is 0,
        which will assign to a random unoccupied port.

    :param bitnami_debug: If enabled, will run the zookeeper and kafka broker in debug mode (`BITNAMI_DEBUG=true`).

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleEndpointService`.

    Has the following additional methods:

    .. method:: connection_port()->int

        Returns the outer port the Kafka broker is listening on.

    .. method:: consumer() -> typing.ContextManager[kafka.KafkaConsumer]

        Creates a kafka consumer for the service and wraps it in a closing context manager.

        .. note:: 
            due to version incompatibility, this methd is only available for python 3.11 and lower

    .. method:: producer() -> typing.ContextManager[kafka.KafkaProducer]

        Creates a kafka producer for the service and wraps it in a closing context manager.

        .. note:: 
            due to version incompatibility, this methd is only available for python 3.11 and lower

