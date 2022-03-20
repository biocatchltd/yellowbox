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

    Specification object for repeated attempts of an arbitrary action that might fail.

    :class:`RetrySpec` is a dataclass. For arguments, see the defined
    attributes.

    .. attribute:: interval
        :type: int | float
        :value: 2

        Time in seconds to pause after a failed attempt. Defaults to 2.


    .. attribute:: attempts
        :type: Optional[int]
        :value: None

        Max number of attempts. If ``None``, infinite attempts are made.

    .. attribute:: timeout
        :type: int | float | None
        :value: None

        A timeout for all the attempts (including the interval) combined. If ``None``, function will never time out.

    .. method:: retry(func, exceptions)->T

        :param func: A no-argument function that may fail with an exception.
        :type func: Callable[[], T]

        :param exceptions: A list of exceptions that ``func`` can raise and that will trigger a retry.
        :type exceptions: Tuple[Type[Exception],...] | Type[Exception]

        Retry the given function until it succeeds according to the :class:`RetrySpec`. Returns the result of the
        ``func`` if it completes successfully. If the maximum number of retries or the timeout is reached, raises the
        last error raises by ``func``.

        .. note::

            If you wish to retry a function that takes arguments, use :func:`functools.partial` to supply the
            arguments.

    .. method:: aretry(func, exceptions)->T
        :async:

        similar to :meth:`retry`, but waits asynchronously between attempts.

    .. code-block::
        :caption: Example Usage

        retry_spec = RetrySpec(interval=0.1, attempts=10)
        try:
            # will attempt to get a URL 10 times, with a 0.1 second interval between attempts
            response = retry_spec.retry(lambda: requests.get('https://www.example.com'),
                                        RequestException)
        except RequestException:
            # all 10 attempts failed
            ...