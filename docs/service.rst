:mod:`service` --- YellowService Main ABC
=====================================================

.. module:: service
    :synopsis: YellowService Main ABC.

-------

Yellowbox's main feature is its :class:`~service.YellowService`, which allows
virtualization of other services, such as
:class:`RabbitMQ <extras.rabbit_mq.RabbitMQService>`,
:class:`Redis <extras.redis.RedisService>`,
:class:`Kafka <extras.kafka.KafkaService>` and more. Each service has its own
set of operations, might run in a docker container or locally, but they all
inherit from :class:`~service.YellowService` and are treated as containerized
units.

.. class:: YellowService

    Abstract base class for defining external services.

    YellowServices can be used as context managers. For example::

        with YellowService().start() as service:
            service.do_stuff()

    Service will automatically stop leaving the context manager.

    .. method:: start()
        :abstractmethod:

        Start the service.

        This method will block until the service is fully up and running.

        Returns the service itself.

    .. method:: stop()
        :abstractmethod:

        Stop the service.

        This method will block until the service is fully stopped.

    .. method:: is_alive()
        :abstractmethod:

        Returns whether the service is currently running.
