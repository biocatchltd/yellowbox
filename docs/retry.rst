:mod:`retry` --- Retrying specification object
=====================================================

.. module:: retry
    :synopsis: Specification object for retrying functions

-------

When starting a :class:`service<service.YellowService>`, Yellowbox waits for the
full initialization of the underlying service (usually docker containers). It
does so by polling a function specific for that service. For example, in case
of :class:`~extras.redis.RedisService`, Yellowbox attempts to connect to the new
Redis server, and :meth:`~subclasses.ContainerService.start` finishes when it
connects successfully.


.. class:: RetrySpec(interval=2, attempts=None, timeout=None)

   Specification object for repeated attempts of an arbitrary action that might
   fail.

    :class:`RetrySpec` is a dataclass. For arguments, see the defined
    attributes.

    .. attribute:: interval

        Time between attempts in seconds. *interval* can be an int or a float.
        Defaults to 2.

    .. attribute:: attempts

        Max number of attempts. If ``None``, infinite attempts are made.

    .. attribute:: timeout

        A timeout for all the attempts (including the interval) combined. If
        ``None``, function will never time out.

    .. method:: retry(func, exceptions)

        Retry the given function until it succeeds according to the
        :class:`RetrySpec`.

        *func* is a no-argument function that may fail with an exception, and
         will be run multiple times according to the spec. If you wish to supply
         arguments to the function, use :func:`functools.partial`.

        *exceptions* is a single exception type or a :class:`tuple` of multiple
         exception types, that will be caught when the function fails.

