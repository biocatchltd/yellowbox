:mod:`clients` --- Docker Clients
=========================================================

.. module:: clients
    :synopsis: Docker Clients.

-------

.. function:: open_docker_client()->contextlib.AbstractContextManager[docker.client.DockerClient]

    Starts a Docker client. Includes a fallback to the default TCP port (and so supports virtual machines like WSL1).

    :return: context manager that yields a valid docker client. And closes it when exiting the context.

.. function:: docker_client(...)

    Legacy alias for :func:`open_docker_client`.