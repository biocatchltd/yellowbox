:mod:`extras.redis` --- Redis Database Service
==============================================

.. module:: extras.redis
    :synopsis: Serving Redis database.

-------

A full-fledged Redis :class:`~service.YellowService` for running the famous
database. Runs the official Redis docker image, with ``redis.py`` as the default
Python client.

.. note::

    If you wish to use this package, please install Yellowbox with the ``redis``
    extra. For more information, see our
    :ref:`installation guide <installation>`.

.. class:: RedisService(docker_client, image="redis:latest", redis_file=None,\
                        **kwargs)

    A :class:`~subclasses.SingleContainerService` used to run the redis
    database.

    *docker_client* is a ``docker.py`` client used to pull the Redis image
    and create the container during instance construction.

    *image* is the Redis database image to use. Defaults to the latest official
    build.

    *redis_file* is a :term:`file-like object` used to load an existing Redis
    database. The file is an RDB file that was dumped earlier on. For more
    information read the official
    `redis manual <https://redis.io/topics/persistence>`_. Defaults to None for a
    fresh database.

    Further `kwargs` are passed to the parent classes' constructor.

    Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`subclasses.RunMixin`.

    Has the following additional methods:

    .. method:: client(*, client_cls = Redis, **kwargs)

        Returns a connected Redis client.

        By default, the client class is a ``redis.py`` Redis object. A callable
        that implements the same interface as the ``redis.py`` Redis constructor
        can be passed as *client_cls*.

        *kwargs* are further keyword arguments that are passed to *client_cls*.
    
    .. method:: client_port()

        Returns the port to be used when connecting to the Redis server.

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
