:mod:`extras.postgresql` --- PostgreSQL Database Service
========================================================

.. module:: extras.postgresql
    :synopsis: Serving PostgreSQL database.

-------

A full-fledged PostgreSQL :class:`~service.YellowService` for running the famous
database. Runs the official PostgreSQL docker image, with ``sqlalchemy`` on top
of ``psycopg2`` as the default Python client.

.. note::

    If you wish to use this package, please install Yellowbox with the
    ``postgresql`` extra. For more information, see our
    :ref:`installation guide <installation>`.

.. class:: PostgreSQLService(docker_client, image="postgres:latest", *,
    user='postgres', password='guest', default_db=None, **kwargs)

    A :class:`~subclasses.SingleContainerService` used to run the Postgres
    database.

    *docker_client* is a ``docker.py`` client used to pull the Postgres image
    and create the container during instance construction.

    *image* is the Postgres database image to use. Defaults to the latest
    official build.

    *user* and *password* are the default username and password to set for
    the server.

    If set, *default_db* would be a name for the default database. Otherwise,
    the default database would be named the same as the username.

    Further `kwargs` are passed to the parent classes' constructor.

    Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`subclasses.RunMixin`.

    Has the following additional methods:

    .. method:: external_port()

        Returns the port to be used when connecting to the Postgres server.

    .. method:: local_connection_string(dialect='postgresql', driver=None,
        database=None)

        Returns an sqlalchemy connection string to the database from the localhost.

        *dialect* is the dialect of the sql server. Defaults to ``'postgresql'``.

        *driver*, if specified, is an additional driver for sqlalchemy to use.

        *database* is the name of the database to connect to. Defaults to the
        service's default database.

        If you wish to connect from a different container, see
        :meth:`container_connection_string`.

    .. method:: container_connection_string(hostname, dialect='postgresql',
        driver=None, database=None)

        Returns an sqlalchemy connection string to the database across containers.

        *hostname* is the alias of the postgres container.

        *dialect* is the dialect of the sql server. Defaults to ``'postgresql'``.

        *driver*, if specified, is an additional driver for sqlalchemy to use.

        *database* is the name of the database to connect to. Defaults to the
        service's default database.

        If you wish to connect from the local docker host, see
        :meth:`local_connection_string`.

    .. method:: connection(**kwargs)

        Creates an SQLAlchemy connection to the default database.

        *kwargs* are extra parameters passed to the
        :meth:`engine.connect <sqlalchemy:engine.connect>` function.

        Returns a :class:`Connection <sqlalchemy:connection>` object.




    .. method:: reset_state()

        Flush the database.

        Equivalent to running ``flushall()`` on a redis client.

    .. method:: set_state(db_dict)

        Set the database to a certain state.

        *db_dict* is a dictionary mapping between string keys used as Redis keys,
        and values. Values can be any of:

        * Primitives - str, int, float, or bytes.
        * Sequence of primitives, for Redis lists.
        * Mapping of field names to primitives, for Redis hashmaps.
