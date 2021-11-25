:mod:`containers` --- Docker Containers Utilities
=========================================================

.. module:: containers
    :synopsis: Docker Containers Utilities.

-------

.. function:: get_ports(container)

    Get the exposed (published) ports of a container.

    :param container: A running container object.
    :type container: :class:`~docker.models.containers.Container`

    :return: A dictionary mapping all internal ports of the container to their external ports on the host machine.
    :rtype: :class:`~collections.abc.Mapping`\[:class:`int`, :class:`int`\]

    .. warning::

        *container* must be running and up to date when calling the function. Ensure the container is up to date by
        calling :meth:`~docker.models.containers.Container.reload`.

.. function:: get_aliases(container, network)

    Get the aliases of a container within a network.

    :param container: A running container object.
    :type container: :class:`~docker.models.containers.Container`

    :param network: The name of the network, or a network object.
    :type network: :class:`str` | :class:`~docker.models.networks.Network`

    :return: A list of aliases of the container in the network.
    :rtype: :class:`~collections.abc.Sequence`\[:class:`str`\]

    .. warning::

        *container* must be running and up to date when calling the function. Ensure the container is up to date by
        calling :meth:`~docker.models.containers.Container.reload`.

.. function:: is_removed(container)

    Check if a container has been removed.

    :param container: A container object.
    :type container: :class:`~docker.models.containers.Container`

    :return: ``True`` if the container has been removed, ``False`` otherwise.
    :rtype: :class:`bool`

.. function:: is_alive(container)

    Check if a container is alive.

    :param container: A container object.
    :type container: :class:`~docker.models.containers.Container`

    :return: ``True`` if the container is alive, ``False`` otherwise.
    :rtype: :class:`bool`

.. function:: killing(container, *, timeout = 10, signal = 'SIGKILL')

    Create a context manager that ensures a container is not running when exiting.

    :param container: A container object.
    :type container: :class:`~docker.models.containers.Container`
    :param float timeout: The timeout in seconds to wait for the container to stop (starting from the context exit).
    :param str | int signal: The signal to send to the container to terminate it.

    :raises: :class:`requests.ReadTimeout` if the container does not stop within the timeout.

    :return: A context manager that yields *container*, and kills the *container* if it is still alive on exit.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`~docker.models.containers.Container`\]

.. function:: create_and_pull(docker_client, image, *args. **kwargs)

    Create a docker container, pulling the image from dockerhub if necessary.

    :param docker_client: A Docker client object.
    :type docker_client: :class:`~docker.client.DockerClient`
    :param str image: The tagged name of the image to pull.
    :param \*args: Positional arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.
    :param \*\*kwargs: Keyword arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.

    :return: A container object.
    :rtype: :class:`~docker.models.containers.Container`

.. function:: download_file(container, path)

    Download a file from a container.

    :param container: A container object.
    :type container: :class:`~docker.models.containers.Container`

    :param path: The path to the file to download (in the container).
    :type path: :class:`str` | :class:`~os.PathLike`

    :return: An IO stream with the file content.
    :rtype: :class:`~typing.IO`\[:class:`bytes`]

    :raises: :exc:`FileNotFoundError` if the file does not exist in the container.
    :raises: :exc:`IsADirectoryError` if the path leads to a directory.

.. function:: upload_file(container, path, data)
              upload_file(container, path, *, fileobj)

    Upload a file to a container.

    :param container: A container object.
    :type container: :class:`~docker.models.containers.Container`
    :pram path: The destination path to upload to (in the container).
    :type path: :class:`str` | :class:`~os.PathLike`
    :param bytes data: The file content to upload.
    :param fileobj: An IO with the file content.
    :type fileobj: :class:`~typing.IO`\[:class:`bytes`]

.. class:: SafeContainerCreator(client)

    A utility class that can create containers and pull images, and can also remove them if subsequent creations fail.

    :param client: A Docker client object to use for pulling images and creating containers.
    :type client: :class:`~docker.client.DockerClient`

    .. method:: create_and_pull(image, command=None, **kwargs)

        Create a container, pulling the image from dockerhub if necessary. If the Container creation fails, all
        containers previously created by the :class:`SafeContainerCreator` are removed.

        :param str image: The tagged name of the image to pull.
        :param str command: The command to run in the container.
        :param \*\*kwargs: Keyword arguments to pass to :meth:`~docker.models.containers.ContainerCollection.create`.

        :return: A container object.
        :rtype: :class:`~docker.models.containers.Container`

        .. note::

            In case of failure, all previously created containers are removed in reverse order to the one they were
            created in.