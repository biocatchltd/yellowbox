:mod:`extras.mssql` --- Microsoft SQL Database Service
========================================================

.. module:: extras.mssql
    :synopsis: Serving Microsoft SQL database.

-------

A :class:`~service.YellowService` for running MSSQL DB. Runs the official Microsoft SQL docker image, with
integration with ``sqlalchemy``.

.. note::

    Requires the ``mssql`` extra. For more information, see our :ref:`installation guide <installation>`. Requires a
    valid mssql driver to be installed.

.. class:: MSSQLService(docker_client: docker.client.DockerClient, image: str="mcr.microsoft.com/mssql/server:latest",\
            *, admin_password: str = 'Swordfish1!', product: str = 'Developer', accept_eula: str | None = None, \
            container_create_kwargs: dict[str, typing.Any] | None = None, **kwargs)

    A service that runs a Microsoft SQL database. Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`~extras.sql_base.SQLService`.

    :param docker_client: The docker client to used to pull and create the Postgresql container.

    :param image: The image name to create a container of.

    :param admin_password: The password for the admin (sa) user.

    :param product: The name of the MSSQL product to create.

    :param accept_eula: Whether to accept the ``product`` EULA. If ``None``, will only accept the EULA if the product
        is ``"Developer"``. See the `image page <https://hub.docker.com/_/microsoft-mssql-server>`_ for more information.

    :param container_create_kwargs: Additional keyword arguments passed to :meth:`docker.models.containers.ContainerCollection.create`.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~extras.sql_base.SQLService`. Note that if no
        local driver specified (or is specified explicitly as ``pyodbc``), and the local options are not specified,
        the local options will be automatically set to target an available local pyodbc driver, and to trust the server
        certificate.
