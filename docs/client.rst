:mod:`clients` --- Docker Clients
=========================================================

.. module:: clients
    :synopsis: Docker Clients.

-------

.. function:: docker_client()

    Starts a Docker client. Includes a fallback to the default TCP port (and so supports virtual machines like WSL1).

    :return: context manager that yields a valid docker client. And closes it when exiting the context.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`~docker.client.DockerClient`\]