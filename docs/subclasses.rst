:mod:`service` --- YellowService Main ABC
=====================================================

.. module:: service
    :synopsis: YellowService Main ABC.

-------

Yellowbox's main feature is it's :class:`~service.YellowService`, which allows
you to virtualize other services, such as
:class:`~extras.rabbit_mq.RabbitMQService <RabbitMQ>`,
:class:`~extras.redis.RedisService <Redis>`,
:class:`~extras.kafka.KafkaService <Kafka>` and more. Each service has it's own
set of operations, might run in a docker container or locally, but they all
inherit from :class:`~service.YellowService` and are treated as containerized
units.

.. class:: YellowService

    Abstract base class for defining external services.

    YellowServices can be used as context managers. For example:

    .. code-block::

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
