:mod:`extras.redis` --- Redis Database Emulation
=====================================================

.. module:: extras.redis
    :synopsis: Emulating Redis database.

-------

A full-fledged Redis :class:`~service.YellowService` for emulating the famous
database. Runs the official Redis docker image, with ``redis.py`` as the default
Python client.

.. class:: RedisService(docker_client, image="redis:latest", redis_file=None)

    A :class:`~subclasses.SingleContainerService` used to emulate the redis
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

    Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`subclasses.RunMixin`. 
