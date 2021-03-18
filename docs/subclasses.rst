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

    *containers* argument is a sequence of docker ``Container`` objects, relevant
    for the service. The containers can come both stopped and started.

    If *remove* is true (default) containers will be removed together with their
    respective volumes when the service is stopped. Same as the attribute
    :attr:`remove`.

    Inherits from :class:`~service.YellowService`.


    .. method:: start(retry_spec=None)
        :abstractmethod:

        Start the service by turning on all stopped containers. Block for it to
        be fully initialized by repeatedly running a certain "check" function,
        chosen by the subclass overriding this method.

        For most services, the chosen function attempts to connect to the
        underlying container until the service is fully started and connection
        is accepted.

        *retry_spec* is a :class:`retry.RetrySpec` instance, specifying the
        internal retry semantics for the chosen "check" function. It allows
        specifying a timeout or maximum number of attempts before startup
        counts as a failure.

    .. method:: stop(signal='SIGTERM')

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

        Returns whether the service is currently running.

    .. method:: connect(network)

        Connect the service to the given docker *network*.

        *network* is a docker.py ``Network`` object.

    .. method:: disconnect(network, **kwargs)

        Disconnect the service from the given *network*.

        *network* is a docker.py `Network` object.

        *kwargs* are extra arguments sent to `Network.disconnect()` of each
        container in the service.

.. class:: SingleEndpointService(containers, remove=True)

    Abstract Base Class for services that have only a single network endpoint.

    One of the containers is used as the endpoint. The container is picked
    internally by the inheriting class.

    Arguments are the same as :class:`ContainerService`.

    Inherits from :class:`ContainerService`.

    The following methods are modified:

    .. method:: connect(network, **kwargs)

        Connects the endpoint to given *network*.

        *network* is a docker.py ``Network`` object.

        *kwargs* are extra arguments passed to the underlying
        `network.connect()`.

    .. method:: disconnect(network, **kargs)

        Disconnect the endpoint from the given *network*.

        *network* is a docker.py ``Network`` object.

        *kwargs* are extra arguments sent to the underlying
        `network.disconnect()`.

.. class:: SingleContainerService(container, remove=True)

    Abstract Base Class for services that are based on a single docker container.

    Inherits from :class:`SingleEndpointService`.

    *container* is a single docker ``Container`` that implements the service.
    Accepts both a started and a stopped container.

    *remove* has the same meaning as in :class:`ContainerService`.

    .. method:: container
        :property:

        Returns the docker ``Container`` implementing the service.

.. class:: RunMixin

    Mixin class implementing a runnable :class:`ContainerService`.

    Adds the convenience method :meth:`run`.

    .. method:: service_name
        :classmethod:

        Returns the service name. May be overridden by subclasses. Defaults
        to ``cls.__name__``.

    .. method:: run(docker_client, *, spinner=True, retry_spec=None, **kwargs)
        :classmethod:

        Convenience method to run the service. Used as a context manager.

        Upon context manager entry, creates the service and starts it. Upon
        exit, stops the service.

        *docker_client* is a ``docker.py`` client used to pull the image from
        dockerhub if it does not exist on the local machine, and for creating
        the container.

        If *spinner* is true (default), shows an indicative text and a beautiful
        spinner in stdout while image is being pulled and service is starting.

        If *retry_spec* is provided, it must be a :class:`retry.RetrySpec`
        object which is passed to :meth:`~ContainerService.start`.

        *kwargs* are further arguments forwarded to the class constructor.
