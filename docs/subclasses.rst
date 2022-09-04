:mod:`subclasses` --- Specialized service ABCs
=====================================================

.. module:: subclasses
    :synopsis: Specialized service ABCs

-------

Yellowbox contains multiple :class:`~service.YellowService` subclasses for
easier definition of services. Most of the subclasses deal with Docker containers
required for running the service.

.. class:: ContainerService(containers: collections.abc.Sequence[docker.models.containers.Container], remove: bool=True)

    Abstract base class for services using one or more docker containers.

    Inherits from :class:`~service.YellowService`.

    Provides basic functionality of turning on the containers on :meth:`start`,
    shutting down and removing the containers on :meth:`stop`, and connecting
    the containers to docker virtual networks using :meth:`connect` and
    :meth:`disconnect`.

    :param containers: A sequence of docker container objects, relevant for the service. The containers may be either
     stopped or started.
    :param remove: Set :attr:`remove`

    .. method:: start(retry_spec: retry.RetrySpec | None = None)
        :abstractmethod:

        Start the service by turning on all stopped containers. Containers are started sequentially in the order provided.

        :param retry_spec: specifies the internal retry semantics for the chosen "check" function.
         It allows specifying a timeout or maximum number of attempts before startup counts as a failure. Subclasses
         should block until the service is responsive using this :class:`~retry.RetrySpec`. If ``None``, subclasses should
         use the a custom default :class:`~retry.RetrySpec`.

    .. method:: stop(signal: str | int='SIGTERM')

        Stop the service with the given *signal*. All containers in the service
        will receive the signal in reverse order. Any container not stopped
        within 10 seconds of receiving the signal will be forcibly closed.

        If :attr:`remove` is true, all containers will be automatically deleted
        together with their respective volumes when the containers are stopped.

        This method will block until all the containers are fully stopped.

        :param signal: The signal to send to the containers.

        .. note::

            Some subclasses override the default signal with something better suited to a specific image (like
            ``'SIGKILL'`` or ``'SIGINT'``).

    .. attribute:: remove
        :type: bool

        If True (default) containers will be removed alongside with
        their respective volumes when the service is stopped. Can also be set
        through the constructor.

    .. method:: is_alive() -> bool

        Returns whether all containers are currently running.

    .. method:: connect(network: docker.models.networks.Network)

        Connect all containers to the given docker network.

        :param network: The network to connect to.

    .. method:: disconnect(network: docker.models.networks.Network, **kwargs)

        Disconnect the service from the given network.

        :param network: The network to disconnect from.

        :param kwargs: Forwarded to :meth:`Network.disconnect<docker.models.networks.Network.disconnect>`
         of each container in the service.

.. class:: SingleEndpointService(containers: collections.abc.Sequence[docker.models.containers.Container], remove: bool=True)

    Abstract Base Class for services that have only a single network endpoint.

    One of the containers is used as the endpoint. The container is picked
    internally by the inheriting class.

    Arguments are the same as :class:`ContainerService`.

    Inherits from :class:`ContainerService`.

    The following methods are modified:

    .. method:: connect(network: docker.models.networks.Network, **kwargs)->Sequence[str]

        Connects the endpoint container to given *network*.

        :param network: The network to connect to.
        :param kwargs: Forwarded to :meth:`Network.connect<docker.models.networks.Network.connect>`.

        :returns: A list of the container's aliases within the network.

    .. method:: disconnect(network: docker.models.networks.Network, **kargs)

        Disconnect the endpoint container from the given network.
        of each container in the service.

        :param network: The network to disconnect from.
        :param kwargs: Forwarded to :meth:`Network.disconnect<docker.models.networks.Network.disconnect>`


.. class:: SingleContainerService(container: docker.models.containers.Container, remove: bool=True)

    Abstract Base Class for services that use a single docker container.

    Inherits from :class:`SingleEndpointService`.

    :param container: A single docker Container that implements the service.
     Accepts both a started and a stopped container.
    :param remove: Same as in :class:`ContainerService`.

    .. method:: container
        :property:

        :type: :class:`docker.Container<docker.models.containers.Container>`

        Returns the docker ``Container`` implementing the service.

.. class:: RunMixin

    Mixin class implementing a runnable :class:`ContainerService`.

    Adds the convenience method :meth:`run`.

    .. method:: service_name()->str
        :classmethod:

        :returns: The name of the service. May be overridden by subclasses. Defaults
         to ``cls.__name__``.

    .. method:: run(docker_client: docker.client.DockerClient, *, spinner: bool=True, \
            retry_spec: retry.RetrySpec | None =None, **kwargs)->contextlib.AbstractContextManager[Self]
        :classmethod:

        Convenience method to run the service. Used as a context manager.

        Upon context manager entry, creates the service and starts it. Upon
        exit, stops the service.

        :param docker_client: The docker client to use to create the containers, or to pull the docker images from
         dockerhub if it does not exist on the local machine.
        :param spinner: If True a spinner is printed to stdout while the image is being pulled and the service is
         starting.
        :param retry_spec: Passed to :meth:`~ContainerService.start`.

        :param kwargs: Forwarded to the class constructor.

.. class:: AsyncRunMixin

    Mixin class implementing a runnable :class:`ContainerService`, whose startup is asynchronous.

    Adds the convenience method :meth:`arun`.

    .. warning::

        Currently, all docker commands are executed synchronously. The only asynchronous part of startup is the time
        waiting between healthcheck attempts.

    .. method:: astart(retry_spec: retry.RetrySpec | None =None)
        :abstractmethod:
        :async:

        Start the service by turning on all stopped containers and waiting for startup. Similar to
        :meth:`ContainerService.start`, but asynchronous.

    .. method:: service_name() -> str
        :classmethod:

        :returns: The name of the service. May be overridden by subclasses. Defaults
         to ``cls.__name__``.

    .. method:: arun(docker_client: docker.client.DockerClient, *, verbose: bool =True, \
            retry_spec: retry.RetrySpec | None=None, **kwargs)->contextlib.AbstractAsyncContextManager[Self]
        :classmethod:

        Convenience method to run the service asynchronously. Used as an async context manager.

        Upon context manager entry, creates the service and starts it. Upon
        exit, stops the service.


        :param docker_client: The docker client to use to create the containers, or to pull the docker images from
         dockerhub if it does not exist on the local machine.

        :param verbose: If True a spinner is printed to stdout while the image is being pulled, and messages are printed
         while the service is starting.

        :param retry_spec: Passed to :meth:`~ContainerService.start`.

        :param kwargs: Forwarded to the class constructor.