:mod:`extras.redis` --- Redis Database Service
==============================================

.. module:: extras.redis
    :synopsis: Serving Redis database.

-------

A :class:`~service.YellowService` for running Redis DB. Runs the official Redis docker image.

.. note::

    Requires the ``redis`` extra. For more information, see our :ref:`installation guide <installation>`.

.. class:: RedisService(docker_client, image="redis:latest", redis_file=None,\
                        **kwargs)

    A service to run the redis database. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin`.

    :param docker_client: The docker client to used to pull and create the Redis container.
    :type docker_client: :class:`docker.DockerClient<docker.client.DockerClient>`

    :param str image: The image name to create a container of.

    :param redis_file: A bytes :term:`file object` for an RDB file used to load an existing Redis database. For more
     information read the official `redis manual <https://redis.io/topics/persistence>`_. Defaults to None for a fresh
     database.
    :type redis_file: :class:`~typing.IO`\[:class:`bytes`]

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: set_rdb(redis_file)

        Load an existing database file onto a redis service.

        :param redis_file: A bytes :term:`file object` for an RDB file used to load an existing Redis database. For more
         information read the official `redis manual <https://redis.io/topics/persistence>`_.
        :type redis_file: :class:`~typing.IO`\[:class:`bytes`]

        .. note::

            Cannot be called while the service is running.


    .. method:: client(*, client_cls = Redis, **kwargs)

        Returns a connected Redis client.

        :param client_cls: The class or callable to use for the client. Defaults to :class:`Redis`.

        :param \*\*kwargs: Additional keyword arguments passed to the client class.
    
    .. method:: client_port() -> int

        Returns the port to be used when connecting to the Redis server from the docker host.

    .. method:: reset_state()

        Remove all keys from the database.
        
        Equivalent to the redis command `FLUSHALL <https://redis.io/commands/FLUSHALL>`_.
    
    .. method:: set_state(db_dict)

        Set the database to a certain state.

        :param db_dict: A Mapping of string keys used as Redis keys TO values. Values can be any of:

         * Primitives - :class:`str`, :class:`int`, :class:`float`, or :class:`bytes`.
         * :class:`~collections.abc.Sequence` of primitives, for Redis lists.
         * :class:`~collections.abc.Mapping` of string field names to primitives, for Redis hashmaps.
        :type db_dict: :class:`~collections.abc.Mapping`\[:class:`str`, ...]
