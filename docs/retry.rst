:mod:`retry` --- Retrying specification object
=====================================================

.. module:: subclasses
    :synopsis: Specification object for retrying functions

-------

When starting :class:`container services<subclasses.ContainerService>`,
Yellowbox waits for the full initialization of the underlying docker containers.
It does so by polling a function specific for that service. For example, in case
of :class:`~extras.redis.RedisService`, Yellowbox attempts to connect to the
new Redis server, and :meth:`~subclasses.ContainerService.start` finishes when
it connects successfully.


.. class:: RetrySpec(interval=2, attempts=None, timeout=None)

   Specification object for repeated attempts of an arbitrary action that might
    fail.

    :class:`RetrySpec` is a dataclass. For arguments, see the defined
    attributes.

    .. attribute:: interval

        Time between attempts in seconds. Defaults to 2.

    .. attribute:: attempts

        Max number of attempts. If ``None``, infinite attempts are made.

    .. attribute:: timeout

        A timeout for all the attempts (including the interval) combined. If
        ``None``, function will never time out.





