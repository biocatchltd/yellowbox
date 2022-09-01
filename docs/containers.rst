:mod:`containers` --- Docker Containers Utilities
=========================================================

.. module:: containers
    :synopsis: Docker Containers Utilities.

-------

.. function:: get_ports(container: docker.models.containers.Container) -> collections.abc.Mapping[int, int]

    Get the exposed (published) ports of a container.

    :param container: A running container object.

    :return: A dictionary mapping all internal ports of the container to their external ports on the host machine.

    .. warning::

        *container* must be running and up to date when calling the function. Ensure the container is up to date by
        calling :meth:`~docker.models.containers.Container.reload`.

.. function:: get_aliases(container: docker.models.containers.Container, network: str | docker.models.networks.Network) -> collections.abc.Sequence[str]

    Get the aliases of a container within a network.

    :param container: A running container object.

    :param network: The name of the network, or a network object.

    :return: A list of aliases of the container in the network.

    .. warning::

        *container* must be running and up to date when calling the function. Ensure the container is up to date by
        calling :meth:`~docker.models.containers.Container.reload`.

.. function:: is_removed(container: docker.models.containers.Container)->bool

    Check if a container has been removed.

    :param container: A container object.

    :return: ``True`` if the container has been removed, ``False`` otherwise.

.. function:: is_alive(container: docker.models.containers.Container)->bool

    Check if a container is alive.

    :param container: A container object.

    :return: ``True`` if the container is alive, ``False`` otherwise.

.. function:: killing(container: docker.models.containers.Container, *, timeout: float = 10, signal: str | int = 'SIGKILL') \
        -> contextlib.AbstractContextManager[docker.models.containers.Container]

    Create a context manager that ensures a container is not running when exiting.

    :param container: A container object.
    :param timeout: The timeout in seconds to wait for the container to stop (starting from the context exit).
    :param signal: The signal to send to the container to terminate it.

    :raises: :class:`requests.ReadTimeout` if the container does not stop within the timeout.

    :return: A context manager that yields *container*, and kills the *container* if it is still alive on exit.

.. function:: removing(container: docker.models.containers.Container, *, \
                expected_exit_code: None | int | typing.Container[int] = 0, force: bool = False) \
                ->contextlib.AbstractContextManager[docker.models.containers.Container]

    Create a context manager that ensures a container is removed when exiting.

    :param container: A container object.
    :param expected_exit_code: The expected exit code (or codes) of the container. If the container exits with a
        different code, an exception will be raised. If ``None``, any exit code is accepted.
    :param force: If ``True``, the container will be removed even if it is still running, or not yet started.

    :raises: :class:`requests.RuntimeError` if the container has not completed with ``force=False``, or if the container
        exited with an unexpected exit code. In these cases, the container is not removed.

    :return: A context manager that yields *container*, and removes the *container* on exit.

.. function:: create_and_pull(docker_client: docker.client.DockerClient, image: str, *args, **kwargs) -> docker.models.containers.Container

    Create a docker container, pulling the image from dockerhub if necessary.

    :param docker_client: A Docker client object.
    :param image: The tagged name of the image to pull.
    :param \*args: Positional arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.
    :param \*\*kwargs: Keyword arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.

    :return: A container object.

.. function:: download_file(container: docker.models.containers.Container, path: str | os.PathLike)->typing.IO[bytes]

    Download a file from a container.

    :param container: A container object.

    :param path: The path to the file to download (in the container).

    :return: An IO stream with the file content.

    :raises: :exc:`FileNotFoundError` if the file does not exist in the container.
    :raises: :exc:`IsADirectoryError` if the path leads to a directory.

.. function:: upload_file(container: docker.models.containers.Container, path: str | os.PathLike, data: bytes)
              upload_file(container: docker.models.containers.Container, path: str | os.PathLike, *, fileobj: typing.IO[bytes])

    Upload a file to a container.

    :param container: A container object.
    :pram path: The destination path to upload to (in the container).
    :param data: The file content to upload.
    :param fileobj: An IO with the file content.

.. class:: SafeContainerCreator(client: docker.client.DockerClient)

    A utility class that can create containers and pull images, and can also remove them if subsequent creations fail.

    :param client: A Docker client object to use for pulling images and creating containers.

    .. method:: create_and_pull(image: str, command: str | None = None, **kwargs) -> docker.models.containers.Container

        Create a container, pulling the image from dockerhub if necessary. If the Container creation fails, all
        containers previously created by the :class:`SafeContainerCreator` are removed.

        :param image: The tagged name of the image to pull.
        :param command: The command to run in the container.
        :param \*\*kwargs: Keyword arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.

        :return: A container object.

        .. note::

            In case of failure, all previously created containers are removed in reverse order to the one they were
            created in.