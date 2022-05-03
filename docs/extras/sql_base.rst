:mod:`extras.sql_base` --- SQL Database Service base class
==========================================================

.. module:: extras.sql_base
    :synopsis: easily creating sql services.

-------

Includes an abstract base class that can be used to easily create SQL services.

.. class:: SQLService(*, local_driver: str | None = None, \
            local_options: typing.Mapping[str, str] | str | None = None , default_database: str)

    Abstract base class for SQL services. Inherits from :class:`~subclasses.SingleEndpointService`,
    :class:`~subclasses.RunMixin`, and :class:`~subclasses.AsyncRunMixin`.

    :param local_driver: the driver to use for local connections by default.
    :param local_options: the options to use for local connections by default.
    :param default_database: the default database to use for connections during startup. Should be a database name that
        is guaranteed to exist during startup.

    .. attribute:: INTERNAL_PORT: int

        The internal port exposed by the service container. Must be set by subclasses.

    .. attribute:: DIALECT: str

        The SQL dialect to use when connecting. Must be set by subclasses.

    .. attribute:: LOCAL_HOSTNAME: str = 'localhost'

        The hostname to use for local connections. Overridable by subclasses.

    .. attribute:: DEFAULT_START_RETRYSPEC: RetrySpec = RetrySpec(attempts=20)

        The default retry spec to use when starting the service. Overridable by subclasses.

    .. method:: userpass() -> typing.Tuple[str, str]
        :abstractmethod:

        Returns a tuple of (username, password) for the service, with admin permissions.

    .. method:: create_database(name: str) -> None

        Creates a database with the given name.

        :raises: :exc:`ValueError` if the database already exists.

    .. method:: drop_database(name: str) -> None

        Drops the database with the given name.

    .. method:: database_exists(name) -> bool

        Returns whether the database with the given name exists.

    .. method:: external_port() -> int

        Returns the external port of the service, respective to its :attr:`INTERNAL_PORT`.

    .. method:: local_connection_string(dialect: str = ..., driver: str | None = ..., *, database: str, \
            options: str | typing.Mapping[str, str] | None = ...) -> str

        Returns a connection string for a local connection to the service. Used to connect to a database from the main
        process.

        :param dialect: The SQL dialect to use. Defaults to :attr:`DIALECT`.
        :param driver: The driver to use. Defaults to the `local_driver` as set in the constructor.
        :param database: The database to connect to.
        :param options: The driver-specific options to use. Defaults to the `local_options` as set in the constructor.
            If is a mapping, all whitespaces in the values will be converted to plus signs.

    .. method:: container_connection_string(hostname: str, dialect: str = ..., driver: str | None = None, *, \
            database: str, options: str | typing.Mapping[str, str] | None = None) -> str

        Returns a connection string for a connection to the service. Used to connect to a database from a container
        over a shared network.

        :param hostname: The hostname of the database container within the shared network.
        :param dialect: The SQL dialect to use. Defaults to :attr:`DIALECT`.
        :param driver: The driver to use. Defaults to `None`.
        :param database: The database to connect to.
        :param options: The driver-specific options to use. Defaults to `None`. If is a mapping, all whitespaces in the
            values will be converted to plus signs.

    .. method:: host_connection_string(dialect: str = ..., driver: str | None = None, *, \
        database: str, options: str | typing.Mapping[str, str] | None = None) -> str

        Returns a connection string for a connection to the service. Used to connect to a database from a container
        over the docker host.

        :param dialect: The SQL dialect to use. Defaults to :attr:`DIALECT`.
        :param driver: The driver to use. Defaults to `None`.
        :param database: The database to connect to.
        :param options: The driver-specific options to use. Defaults to `None`. If is a mapping, all whitespaces in the
            values will be converted to plus signs.

    .. method:: database(name: str) -> Database

        Returns a database with the given name. Will create the database if it does not exist.

        .. note::

            can be used as a context manager, to ensure deletion of the database.

            .. code-block:: python

                with service.database('my_database') as db:
                    assert service.database_exists('my_database')
                    ...
                assert not service.database_exists('my_database')

.. class:: Database

    Represents a database within an SQL service. Created by the :meth:`SQLService.database` method. Can be used as a
    context manager, to ensure deletion of the database.

    .. note::

        In most cases, a Database instance ensures that the database exists when it is created. However it is possible
        to drop the database after the instance is created. Users should take care to not drop a database that is
        referenced by a live Database instance.

    .. method:: local_connection_string(...)->str
                container_connection_string(...)->str
                host_connection_string(...)->str

        Returns a connection string for a connection to the database. All parameters are the same as in the
        corresponding :class:`SQLService` method, except for `database`, which is the same as name of the database.

    .. method:: __exit__(...)

        Deletes the database.
