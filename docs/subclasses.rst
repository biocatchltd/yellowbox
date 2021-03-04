:mod:`subclasses` --- Specialized service ABCs
=====================================================

.. module:: subclasses
    :synopsis: Specialized service ABCs

-------

Yellowbox contains multiple :class:`~service.YellowService` subclasses for
easier definition of services. Most of the subclasses deal with Docker containers
required for running the service.

.. class:: ContainerService(containers, remove=True)

    Abstract base class for services using any number of docker containers.

    Provides basic functionality of turning on the containers on :meth:`start`,
    shutting down and removing the containers on :meth:`stop`, and connecting
    the containers to docker virtual networks using :meth:`connect` and
    :meth:`disconnect`.

    *containers* argument is a sequence of docker `Container` objects, relevant for the
    service. The containers can come both stopped and started.

    If *remove* is true (default) containers will be removed together with their
    respective volumes when the service is stopped. Same as the attribute
    :attr:`remove`.

    Inherits from :class:`~service.YellowService`.


    .. method:: start()
        :abstractmethod:

        Start the service by turning on all stopped containers.

    .. method:: stop(signal='SIGTERM')
        :abstractmethod:

        Stop the service with the given *signal*. All containers in the service
        will receive the signal in reverse order. Any container not stopped
        within 10 seconds of receiving the signal will be forcibly closed.

        If :attr:`remove` is true, all containers will be automatically deleted
        together with their respective volumes when the containers are stopped.

        This method will block until the service is fully stopped.

    .. attribute:: remove

        If *remove* is true (default) containers will be removed together with
        their respective volumes when the service is stopped. Can also be set
        through the constructor.

    .. method:: is_alive()
        :abstractmethod:

        Returns whether the service is currently running.
