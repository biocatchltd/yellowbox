:mod:`extras.websocket` --- Simple Websocket Server (Deprecated)
============================================================================

.. module:: extras.websocket
    :synopsis: Simple Websocket Server.

-------

An HTTP :class:`~service.YellowService` used to easily mock and test websocket connections.

.. deprecated:: 0.6.6
    Use :class:`~extras.http_server.webserver` instead.

.. note::

    Requires the ``websocket`` extra. For more information, see our :ref:`installation guide <installation>`.

.. code-block::
    :caption: Setting up an example websocket server

    service = WebsocketService()
    # Let's write "Hello!" to the websocket upon connection to the "/hello"
    # endpoint:
    service.add("Hello!", "/hello")
    # We'll also make a simple echo endpoint:
    @service.route("/echo")
    def echo(websocket):
        data = None
        while True:
            # Yield sends out the data, and waits for incoming data.
            data = yield data

    service.start()

.. class:: WebsocketService()

    A Simple WS server wrapped as :class:`~service.YellowService`.

    Inherits from :class:`~service.YellowService`.

    .. attribute:: port
        :type: int

        Read-only attribute denoting the websocket port of the service.

    .. property:: local_url
        :type: str

        Full URL to access the WS Server from localhost (including port).

    .. property:: container_url
        :type: str

        Full URL to access the WS Server from inside a locally-running
        container (including port).

    .. method:: add(side_effect, path=None, *, regex=None)

        Add a new route to the service.

        :param side_effect: The response for when the route is accessed, can be one of:

            * A primitive value, one of ::class:`str`, :class:`bytes`, :class:`bytearray` or :class:`memoryview`, which
              will be sent to the client and the connection closed.
            * The ``None`` primiitve, indicating that the websocket should close.
            * An iterable of any combination of the above primitive types, which will be sent one by one to the client,
              waiting for messages between any two.
            * A :class:`~collections.abc.Callable` which will be called with the `Simple Websocket
              <https://github.com/pikhovkin/simple-websocket-server>`_ object as the argument. The function should
              return a primitive value, the value will be sent to the client and the connection closed.
            * A :class:`~collections.abc.Callable` which returns a :term:`generator`. The callable will be called with the
              `Simple Websocket <https://github.com/pikhovkin/simple-websocket-server>`_ object as the argument. The
              generator should yield primitive values, which will be sent to the client and between receiving data.

        :param str | None path: The path to match the route against. Omit if using regex.
        :param regex: The path pattern to match the route against. Omit if using path.
        :type regex: :class:`str` | :class:`~typing.Pattern`\[:class:`str`] | :data:`None`

        .. note::

            exactly one of ``path`` or ``regex`` must be specified.

        :raises RuntimeError: If the path already exists.

    .. method:: route(path = None, *, regex = None)

        A decorator to add a route to the service.

        .. code-block:: python

            @service.route("/echo")
            def echo(websocket):
                data = None
                while True:
                    data = yield data

        `path` and `regex` parameters are the same as :meth:`.add`.

    .. method:: set(side_effect, path=None, *, regex=None)

        Set a new route or replace an existing route to the service.

        Parameters are the same as :meth:`.add`.

    .. method:: patch(side_effect, path=None, regex=None) -> typing.ContextManager

        returns a context manager that adds a route to the service on entry and removes it on exit.

        Parameters are the same as :meth:`.add`.

    .. method:: remove(path = None, *, regex = None)

        Remove a route from the service.

        :param str | None path: The path of the route that was previously inserted. Omit if using regex.
        :param regex: The path pattern of the route that was previously inserted. Omit if using path.
        :type regex: :class:`str` | :class:`~typing.Pattern`\[:class:`str`] | :data:`None`

        .. note::

            exactly one of ``path`` or ``regex`` must be specified.

        :raises KeyError:  if the route is not found.

    .. method:: clear()

        Remove all routes from the service.



