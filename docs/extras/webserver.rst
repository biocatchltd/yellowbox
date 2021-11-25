:mod:`extras.webserver` --- Web Server
=========================================================
.. include:: <isonum.txt>

.. module:: extras.webserver
    :synopsis: Web Server.

-------

.. note::

    Requires the ``webserver`` extra. For more information, see our :ref:`installation guide <installation>`.

A simple `Starlette, <https://www.starlette.io/>`_ web server running on `Unicorn <https://www.uvicorn.org/>`_. Capable
of handling both HTTP and websocket routes.

.. note:: Errors in side-effects.

    Since the server (and handlers for all routes) is running in a separate thread, any errors in side-effects will not
    be immediately caught by the main thread. Instead, all unhandled errors in routes will be stored by the Webservice
    and re-raised when some methods of the WebServer, or methods of endpoints linked to the webserver, are called
    (see :exc:`HandlerError`). These methods are:

    * :meth:`WebServer.add_http_endpoint`
    * :meth:`WebServer.remove_http_endpoint`
    * :meth:`WebServer.patch_http_endpoint`
    * :meth:`WebServer.add_ws_endpoint`
    * :meth:`WebServer.remove_ws_endpoint`
    * :meth:`WebServer.patch_ws_endpoint`
    * :meth:`WebServer.stop <service.YellowService.stop>`
    * :meth:`WebServer.is_alive <service.YellowService.is_alive>`
    * :meth:`MockHTTPEndpoint.patch`
    * :meth:`MockHTTPEndpoint.capture_calls`
    * :meth:`MockWSEndpoint.patch`
    * :meth:`MockWSEndpoint.capture_calls`

    Also, if such an error is encountered, all future calls to any route in the service will return Error Code 500.


.. class:: WebServer(name, port=None, **kwargs)

    A uvicorn-starlette web server that supports on-the-fly adding and removing of routes.

    :param str name: The name of the server, used for logging and debugging.
    :param int | None port: The port to bind to when serving, default will bind to an available port.
    :param \*\*kwargs: Additional keyword arguments to pass to the starlette server's `uvicorn configuration
     <https://github.com/encode/uvicorn/blob/master/uvicorn/config.py>`_.

    .. note::

        unless overridden in *\*\*kwargs*, the following values differ from uvicorn's defaults:

        * ``host``: changed to ``'0.0.0.0'``
        * ``log_config``: Changed to a logging config that resembles the default and also includes the server name in
          its log messages.

    .. property:: port
        :type: int | None

        The port the server is bound to. If the port was specified in construction, this will be the same. Otherwise, if
        the server was not started, this will be ``None``. If the server is started and bound to a port, this will be
        the port it is bound to. If the server is started but not yet bound to a port, this property will block for at
        most 1 second, waiting for the binding to complete.

        :raises RuntimeError: If the binding process takes more than 1 second.

    .. method:: add_http_endpoint(endpoint)
                add_http_endpoint(methods, rule_string, side_effect, *, auto_read_body=True,\
                                  forbid_implicit_head_verb = True)

        Add an HTTP endpoint to the server. Can accept either a created endpoint or arguments to create one.

        :param endpoint: The endpoint to add, as returned by :func:`http_endpoint`.
        :type endpoint: :class:`MockHttpEndpoint`
        :Other Parameters: Used to create a new endpoint (forwarded to :func:`http_endpoint`).

        :returns: The endpoint that was added, to be used as a decorator.
        :rtype: :class:`MockHTTPEndpoint`

        .. code-block::
            :caption: Example with decorator syntax.

            @server.add_http_endpoint
            @http_endpoint('GET', '/square/{x:int}')
            async def square(request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            assert get(server.local_url() + '/square/12').text == '144'

        .. code-block::
            :caption: Example for creating a new endpoint.

            endpoint = server.add_http_endpoint('GET', 'ping', PlainTextResponse('pong'))

            assert get(server.local_url() + '/ping').text == 'pong'

    .. method:: remove_http_endpoint(endpoint)

        Remove an HTTP endpoint previously added to the server.

        :param endpoint: The endpoint to remove.
        :type endpoint: :class:`MockHttpEndpoint`

        :raises RuntimeError: If the endpoint is not added to the server.

    .. method:: patch_http_endpoint(endpoint)
                patch_http_endpoint(methods, rule_string, side_effect, *, auto_read_body=True,\
                                    forbid_implicit_head_verb = True)

        Add to, then remove an HTTP endpoint from the server within a context. Can accept either a created
        endpoint or arguments to create one.

        :param endpoint: The endpoint to add, as returned by :func:`http_endpoint`.
        :type endpoint: :class:`MockHttpEndpoint`
        :Other Parameters: Used to create a new endpoint (forwarded to :func:`http_endpoint`).

        :returns: A context manager that adds and yields the endpoint upon entry, and removes it upon exit.
        :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`MockHTTPEndpoint`\]

        .. code-block::
            :caption: Example

            @http_endpoint('GET', '/square/{x:int}')
            async def square(request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            with server.patch_http_endpoint(square):
                assert get(server.local_url() + '/square/12').text == '144'

            # when the context is exited, the endpoint is removed
            assert get(server.local_url() + '/square/12').status_code == 404

    .. method:: add_ws_endpoint(endpoint)
                add_ws_endpoint(rule_string, side_effect)

        Add an HTTP endpoint to the server. Can accept either a created endpoint or arguments to create one.

        :param endpoint: The endpoint to add, as returned by :func:`ws_endpoint`.
        :type endpoint: :class:`MockWSEndpoint`
        :Other Parameters: Used to create a new endpoint (forwarded to :func:`ws_endpoint`).

        :returns: The endpoint that was added, to be used as a decorator.
        :rtype: :class:`MockWSEndpoint`

        .. code-block::
            :caption: Example with decorator syntax.

            @server.add_ws_endpoint
            @ws_endpoint('/moria')
            async def moria(websocket):
                await websocket.accept()
                await websocket.send_text('Speak, friend, and enter')
                if await websocket.receive_text() == 'Mellon':
                    return WS_1000_NORMAL_CLOSURE
                else:
                    return WS_1008_POLICY_VIOLATION

            ws_client = websocket.create_connection(server.local_url('ws') + '/moria')
            assert ws_client.recv() == 'Speak, friend, and enter'
            ws_client.send('Mellon')

    .. method:: remove_ws_endpoint(endpoint)

        Remove a websocket endpoint previously added to the server.

        :param endpoint: The endpoint to remove.
        :type endpoint: :class:`MockWSEndpoint`

        :raises RuntimeError: If the endpoint is not added to the server.

    .. method:: patch_ws_endpoint(endpoint)
                patch_ws_endpoint(rule_string, side_effect)

        Add to, then remove a websocket endpoint from the server within a context. Can accept either a created
        endpoint or arguments to create one.

        :param endpoint: The endpoint to add, as returned by :func:`ws_endpoint`.
        :type endpoint: :class:`MockWSEndpoint`
        :Other Parameters: Used to create a new endpoint (forwarded to :func:`ws_endpoint`).

        :returns: A context manager that adds and yields the endpoint upon entry, and removes it upon exit.
        :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`MockWSEndpoint`\]

    .. method:: local_url(schema = 'http')

        Get the URL to access the server from the local machine, with the given schema.

        :param str | None schema: The schema to use. On ``None``, returns a URL without a schema.
        :returns: The URL of the server.
        :rtype: :class:`str`

    .. method:: container_url(schema = 'http')

        Get the URL to access the server from a docker container, with the given schema.

        :param str | None schema: The schema to use. On ``None``, returns a URL without a schema.
        :returns: The URL of the server.
        :rtype: :class:`str`

.. function:: http_endpoint(methods, rule_string, side_effect, *, auto_read_body=True, forbid_implicit_head_verb = True)
              http_endpoint(methods, rule_string, *, auto_read_body=True, forbid_implicit_head_verb = True)

    Create an HTTP endpoint to link to a :class:`Webserver` (see :meth:`WebServer.add_http_endpoint`).

    :param methods: The HTTP method or methods to allow into the endpoint (case insensitive).
    :type methods: :class:`str` | :class:`~collections.abc.Iterable`\[:class:`str`\]
    :param str rule_string: The URL rule string as specified by `Starlette URL rule specs
     <https://www.starlette.io/routing/#path-parameters>`_.
    :param side_effect: The side effect to execute when the endpoint is requested. Can either be a `Starlette response
     <https://www.starlette.io/responses/>`_, in this case the response will always be returned, or an async callable
     that accepts a positional `Starlette Request <https://www.starlette.io/requests/>`_ and returns a `Starlette
     response <https://www.starlette.io/responses/>`_. Can be delegated as a decorator.
    :type side_effect: `Response`_ | async `Request <https://www.starlette.io/requests/#request>`_ |rarr| `Response`_
    :param bool auto_read_body: By default, Starlette may begin to respond to requests before the request body has fully
     arrived to the server. This may cause race condition issues on local hosts. This param (enabled by default) ensures
     that the entire request arrives to the server before a response is returned.
    :param bool forbid_implicit_head_verb: By default for Starlette routes, if the ``GET`` method is allowed for a route
     , the ``HEAD`` method will also be allowed. This param (enabled by default) disables this behavior.
    :returns: The a new HTTP endpoint that can be added to a Webservice.
    :rtype: :class:`MockHTTPEndpoint`

    .. note::
        this function can be used a decorator by omitting *side_effect*.

        .. code-block::
            :caption: Example with decorator syntax.

            @http_endpoint('GET', '/square/{x:int}')
            async def square(request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            # is equivalent to:

            async def square(request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            square = http_endpoint('GET', '/square/{x:int}', square)

    .. note::

        In order to use a "rotating" side effect (i.e. one that returns a different response per request), see
        :func:`iter_side_effects`.

.. function:: ws_endpoint(rule_string, side_effect)
              ws_endpoint(rule_string)

    Create a WebSocket endpoint to link to a :class:`Webserver` (see :meth:`WebServer.add_ws_endpoint`).

    :param str rule_string: The URL rule string as specified by `Starlette URL rule specs
     <https://www.starlette.io/routing/#path-parameters>`_.
    :param side_effect: The side effect to execute when the endpoint is requested. Should be an async callable that
     accepts a positional `Starlette WebSocket <https://www.starlette.io/websockets/#websocket>`_. If the callable
     returns an integer, the connection is closed with that exit code. Can be delegated as a decorator.
    :type side_effect: async `WebSocket <https://www.starlette.io/websockets/#websocket>`_ |rarr| (int | None)
    :returns: The a new Websocket endpoint that can be added to a Webservice.
    :rtype: :class:`MockWSEndpoint`

    .. note::
        this function can be used a decorator by omitting *side_effect*.

        .. code-block::
            :caption: Example with decorator syntax.

            @ws_endpoint('/square')
            async def square(ws: WebSocket):
              await ws.accept()
              x = int(await ws.receive_text())
              await ws.send_text(str(x*x))
              await ws.close()

            # is equivalent to:

            async def square(ws: WebSocket):
              await ws.accept()
              x = int(await ws.receive_text())
              await ws.send_text(str(x*x))
              await ws.close()

            square = ws_endpoint('/square', square)

    .. note::

        In order to use a "rotating" side effect (i.e. one that returns a different response per request), see
        :func:`iter_side_effects`.

.. class:: MockHTTPEndpoint

    An HTTP endpoint that can be added to a :class:`Webserver` (see :meth:`WebServer.add_http_endpoint`). construct with
    :func:`http_endpoint`.

    .. method:: patch(side_effect)

        Change the side effect of the endpoint. With the ability to revert it to the original side effect.

        :param side_effect: The new side effect to execute when the endpoint is requested. Accepts the same types as
         :func:`http_endpoint`.
        :returns: A context manager that reverts the endpoint's side effect to the original value, if ever exited.

        .. code-block::
            :caption: Example.

            mock_http_endpoint = http_endpoint('GET', '/ping', PlainTextResponse('pong'))
            # the endpoint will return 'pong' if called now
            with mock_http_endpoint.patch(PlainTextResponse('pang')):
                # the endpoint will return 'pang' if called now
                ...
            # the endpoint will return 'pong' if called now
            mock_http_endpoint.patch(PlainTextResponse('powong'))
            # the endpoint will return 'powong' if called now

        .. warning::
            .. _out of order patch:

            Because the patch takes effect immediately, but is reversible via context management, using multiple
            patches out of order can have unexpected results.

            .. code-block::

                mock_http_endpoint = http_endpoint('GET', '/color', PlainTextResponse('red'))
                # side effect is now 'red'
                patch1 = mock_http_endpoint.patch(PlainTextResponse('green'))
                # side effect is now 'green'
                patch2 = mock_http_endpoint.patch(PlainTextResponse('blue'))
                # side effect is now 'blue'
                with patch1:
                    # side effect is now *still* 'blue'
                    ...
                # side effect is now 'red'
                with patch2:
                    # side effect is now *still* 'red'
                    ...
                # side effect is now 'green'

            Therefore, it is best practice to always either discard the return value of this function, or immediately
            enter its context

    .. method:: capture_calls()

        Capture all calls to the endpoint within a context.

        :returns: context manager that begins capturing all calls to endpoint on entry and stops recording on exit, all
         captured calls are recorded on the yielded :class:`RecordedHTTPRequests`.
        :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`RecordedHTTPRequests`\]

        .. code-block::
            :caption: Example.

            @server.add_http_endpoint
            @http_endpoint('GET', '/square/{x:int}')
            async def square(request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            with square.capture_calls() as calls:
                assert get(server.local_url() + '/square/12').text == '144'
                assert get(server.local_url() + '/square/11').text == '121'

            calls.assert_has_requests(
                ExpectedHTTPRequest(path_params={'x': 12}),
                ExpectedHTTPRequest(path_params={'x': 11})
            )

        .. note::

            ``auto_read_body`` must be enabled to capture calls.

.. class:: MockWSEndpoint

    A websocket endpoint that can be added to a :class:`Webserver` (see :meth:`WebServer.add_ws_endpoint`). construct
    with :func:`ws_endpoint`.

    .. method:: patch(side_effect)

        Change the side effect of the endpoint. With the ability to revert it to the original side effect.

        :param side_effect: The new side effect to execute when the endpoint is requested. Accepts the same types as
         :func:`ws_endpoint`.
        :returns: A context manager that reverts the endpoint's side effect to the original value, if ever exited.

        .. warning::

            See the :ref:`out-of-order warning in MockHTTPEndpoint.patch <out of order patch>`.

    .. method:: capture_calls()

        Capture all calls to the endpoint within a context.

        :returns: context manager that begins capturing all calls to endpoint on entry and stops recording on exit, all
         captured calls are recorded on the yielded :class:`RecordedWSTranscripts`.
        :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`RecordedWSTranscripts`\]

.. _Response: https://www.starlette.io/responses/#response

.. function:: class_http_endpoint(methods, rule_string, side_effect, *, auto_read_body=True, \
                                  forbid_implicit_head_verb = True)
              class_http_endpoint(methods, rule_string, *, auto_read_body=True, forbid_implicit_head_verb = True)
              class_ws_endpoint(rule_string, side_effect)
              class_ws_endpoint(rule_string)

    Create an endpoint template. Declare this in a :class:`WebServer` subclass body to automatically add an
    endpoint to all instances of the subclass.

    All arguments are the same as :func:`http_endpoint` and :func:`ws_endpoint`.

    .. code-block::
        :caption: Example.

        class MyWebServer(WebServer):
            @class_http_endpoint('GET', '/hello')
            async def hello(self, request):
                return PlainTextResponse('Hello, World!')

            @class_ws_endpoint('/echo')
            async def echo(self, websocket):
                await websocket.accept()
                while True:
                    message = await websocket.receive_text()
                    await websocket.send_text(message)

        server = MyWebServer("my name").start()

        assert get(server.local_url() + '/hello').text == 'Hello, World!'

        async with websocket_connect(server.local_url() + '/echo') as websocket:
            await websocket.send_text('Hello, World!')
            assert await websocket.receive_text() == 'Hello, World!'

.. class:: ExpectedHTTPRequest(headers=None, headers_submap=None, path=None, path_params=None, path_params_submap=None,\
           query_params=None, query_params_submap=None,method=None, body=None, text=None, json =...,\
           content_predicate=None)

    An expected HTTP request, used for matching a recorded request.

    :param headers: If specified, a recorded request must have the specified headers exactly.
    :type headers: :class:`~collections.abc.Mapping`\[:class:`bytes`,
        :class:`~collections.abc.Collection`\[:class:`bytes`\]\]
    :param headers_submap: If specified, a recorded request must have at least the specified headers.
    :type headers_submap: :class:`~collections.abc.Mapping`\[:class:`bytes`,
        :class:`~collections.abc.Collection`\[:class:`bytes`\]\]
    :param path: If specified, a recorded request must have the specified path exactly (if :class:`str`), or must match
        the specified pattern fully (if :class:`~typing.Pattern`).
    :type path: :class:`str` | :class:`~typing.Pattern`\[:class:`str`]
    :param path_params: If specified, a recorded request must have the specified path parameters exactly.
    :type path_params: :class:`~collections.abc.Mapping`\[:class:`str`, ...\]
    :param path_params_submap: If specified, a recorded request must have at least the specified path parameters.
    :type path_params_submap: :class:`~collections.abc.Mapping`\[:class:`str`, ...\]
    :param query_params: If specified, a recorded request must have the specified query parameters exactly.
    :type query_params: :class:`~collections.abc.Mapping`\[:class:`str`,
        :class:`~collections.abc.Collection`\[:class:`str`\]\]
    :param query_params_submap: If specified, a recorded request must have at least the specified query parameters.
    :type query_params_submap: :class:`~collections.abc.Mapping`\[:class:`str`,
        :class:`~collections.abc.Collection`\[:class:`str`\]\]
    :param str method: If specified, a recorded request must be of the specified HTTP method (case-insensitive).
    :param bytes body: If specified, a recorded request must have a body equal to the one specified.
    :param str text: If specified, a recorded request must have a body equal to the one specified with utf-8 encoding.
    :param json: If specified, a recorded request must have a body equal to the one specified with json encoding.
    :param content_predicate: If specified, may be a callable that accepts a :class:`bytes` object, in which
        case the predicate must evaluate to True when called with the request body. Alternatively, the predicate can be
        a tuple of a callable that returns a value, and a value to compare to, in this case, the callable must return
        the value specified when called with the request body.

    .. note::

        Only one of ``body``, ``text``, ``json``, or ``content_predicate`` may be specified. Additionally, only a
        parameter or its ``*_submap`` variant may be specified, but not both.

.. class:: http_request_capture.RecordedHTTPRequests

    A :class:`list` of recorded HTTP requests. Yielded by :meth:`MockHttpEndpoint.capture_calls` to record requests.

    .. method:: assert_not_requested()

        Assert that no requests were made.

        :raises AssertionError: If any requests were made.

    .. method:: assert_requested()

        Assert that at least one request was made.

        :raises AssertionError: If no requests were made.

    .. method:: assert_requested_once()

        Assert that exactly one request was made.

        :raises AssertionError: If no or multiple request were made.

    .. method:: assert_requested_with(expected)
                assert_requested_with(**kwargs)

        Assert that the latest request was made matches an expected request.

        :param expected: The expected request.
        :type expected: :class:`ExpectedHTTPRequest`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected request
            parameters as keyword arguments.
        :raises AssertionError: If the last request doesn't match the expected request, or if there are no requests.

        .. code-block::
            :caption: Example
            :name: skip expected creation


            recorded: RecordedHTTPRequests = ...

            recorded.assert_requested_with(ExpectedHTTPRequest(
                content_predicate = (lambda b:b.decode('utf-7'), 'hi'),
            ))

            # is equivelant to
            recorded.assert_requested_with(
                content_predicate = (lambda b:b.decode('utf-7'), 'hi'),
            )

    .. method:: assert_requested_once_with(expected)
                assert_requested_once_with(**kwargs)

        Assert that only one request was made, and that it matches an expected request.

        :param expected: The expected request.
        :type expected: :class:`ExpectedHTTPRequest`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected request
            parameters as keyword arguments (see :ref:`the example in assert_requested_with <skip expected creation>`).
        :raises AssertionError: If there are more than one or no requests made, or if the only request does not match
            the קספקבאקג request.

    .. method:: assert_any_request(expected)
                assert_any_request(**kwargs)

        Assert that a request was made that matches an expected request.

        :param expected: The expected request.
        :type expected: :class:`ExpectedHTTPRequest`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected request
            parameters as keyword arguments (see :ref:`the example in assert_requested_with <skip expected creation>`).
        :raises AssertionError: If no request that matches the expectation was made.

    .. method:: assert_has_requests_any_order(*expected_requests)

        Assert that a set of expected requests were made, in any order.

        :param \*expected: The expected requests to match.
        :type \*expected: :class:`ExpectedHTTPRequest`

        :raises AssertionError: If any of the expected requests were not made.

        .. note::

            Each expected request must match **exclusively** to a recorded request, meaning that there must be at least as
            many recorded requests as expected requests.

            .. code-block::
                :caption: Example of exclusivity requirements

                endpoint = server.add_http_endpoint('/', PlainTextResponse('hi'))
                with endpoint.capture_calls as recorded:
                    get(server.local_url()+'/', headers={'A':'B'})

                # the following will raise an AssertionError
                recorded.assert_has_requests_any_order(
                    ExpectedHTTPRequest(method='GET'),
                    ExpectedHTTPRequest(headers={b'A':[b'B']}),
                )

    .. method:: assert_has_requests(*expected_requests)

        Assert that a set of expected requests were made, in sequential order.

        :param \*expected: The expected requests to match.
        :type \*expected: :class:`ExpectedHTTPRequest`

        :raises AssertionError: If the expected requests were not matched in sequential order.

.. class:: Sender

    An Enum class for two senders in a Websocket connection. Used to create an expected websocket message.

    .. attribute:: Client
                   Server

        A sender of a message to the recipient.

    .. method:: __call__(data)

        Create an expectation of a websocket message from the given data, as sent by the given sender.

        :param data: The payload of the expected message. Can be one of:

            * :class:`str`: A string expected to be the payload.
            * :class:`bytes`: A bytes expected to be the payload.
            * :class:`~typing.Pattern`\[:class:`bytes` | :class:`str`\]: A pattern that the payload is expected to fully
              match.
            * :data:`Ellipsis`: A special value that matches any payload.

.. class:: ExpectedWSTranscript(messages=(...,), headers=None, headers_submap=None, path=None, path_params=None,\
                                path_params_submap=None, query_params=None, query_params_submap=None, close=None, \
                                accepted=None)

    An expectation of a websocket transcript. Used to match against a recorded websocket transcript.

    :param messages: The expected messages in the transcript, in order. Create an expected message by calling
        :class:`Sender`. The sequence may begin or end with :data:`Ellipsis` to signify that any number of messages can
        precede or follow the messages to match.
    :type messages: :class:`~collections.abc.Sequence`\[:class:`Sender`\(...\) | :data:`Ellipsis`\]
    :param headers: If specified, a recorded request must have the specified headers exactly.
    :type headers: :class:`~collections.abc.Mapping`\[:class:`bytes`,
        :class:`~collections.abc.Collection`\[:class:`bytes`\]\]
    :param headers_submap: If specified, a recorded request must have at least the specified headers.
    :type headers_submap: :class:`~collections.abc.Mapping`\[:class:`bytes`,
        :class:`~collections.abc.Collection`\[:class:`bytes`\]\]
    :param path: If specified, a recorded request must have the specified path exactly (if :class:`str`), or must match
        the specified pattern fully (if :class:`~typing.Pattern`).
    :type path: :class:`str` | :class:`~typing.Pattern`\[:class:`str`]
    :param path_params: If specified, a recorded request must have the specified path parameters exactly.
    :type path_params: :class:`~collections.abc.Mapping`\[:class:`str`, ...\]
    :param path_params_submap: If specified, a recorded request must have at least the specified path parameters.
    :type path_params_submap: :class:`~collections.abc.Mapping`\[:class:`str`, ...\]
    :param query_params: If specified, a recorded request must have the specified query parameters exactly.
    :type query_params: :class:`~collections.abc.Mapping`\[:class:`str`,
        :class:`~collections.abc.Collection`\[:class:`str`\]\]
    :param query_params_submap: If specified, a recorded request must have at least the specified query parameters.
    :type query_params_submap: :class:`~collections.abc.Mapping`\[:class:`str`,
        :class:`~collections.abc.Collection`\[:class:`str`\]\]
    :param close: If specified, the transcript closing must have been done by the specified sender, and with the
        specified code.
    :type close: (:class:`Sender`, :class:`int`)
    :param bool accepted: If specified, the connection must have been accepted by the server (if True), or rejected by
        the server (if False).

    .. note::

        Only a parameter or its ``*_submap`` variant may be specified, but not both.

    .. code-block::
        :caption: Example usage

        expected_transcript = ExpectedWSTranscript([
            Sender.Server(b'hi there, what is your name?'),
            Sender.Client(re.compile(b'My name is [A-Z][a-z]+')),
            Sender.Client(b'And I like pie'),
            ...
        ], close=(Sender.Server, 1000))

        # requires that the transcript will begin with the server sending 'hi
        # there, what is your name?', then the client should respond with a
        # name, then the client should respond with 'And I like pie'. Any
        # number of messages can follow after that, but eventually the server
        # should close the connection with code 1000.

.. class:: ws_request_capture.RecordedWSTranscripts

    A :class:`list` of recorded websocket requests. Yielded by :meth:`MockWSEndpoint.capture_calls` to record
    transcripts.

    .. method:: assert_not_requested()

        Assert that no connections were made.

        :raises AssertionError: If any connections were made.

    .. method:: assert_requested()

        Assert that at least one connection was made.

        :raises AssertionError: If no connections were made.

    .. method:: assert_requested_once()

        Assert that exactly one connection was made.

        :raises AssertionError: If no or multiple connections were made.

    .. method:: assert_requested_with(expected)
                assert_requested_with(**kwargs)

        Assert that the latest connections was made matches an expected transcript.

        :param expected: The expected connection.
        :type expected: :class:`ExpectedWSTranscript`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected transcript
            parameters as keyword arguments.
        :raises AssertionError: If the last transcript doesn't match the expected request, or if there are no transcript.

    .. method:: assert_requested_once_with(expected)
                assert_requested_once_with(**kwargs)

        Assert that only one connection was made, and that it matches an expected transcript.

        :param expected: The expected connection.
        :type expected: :class:`ExpectedWSTranscript`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected request
            parameters as keyword arguments.
        :raises AssertionError: If there are more than one or no connections made, or if the only transcript does not
            match the expectation.

    .. method:: assert_any_request(expected)
                assert_any_request(**kwargs)

        Assert that a connection was made that matches an expected transcript.

        :param expected: The expected connection.
        :type expected: :class:`ExpectedWSTranscript`
        :param \*\*kwargs: Alternatively, users can skip the ``expected`` argument and specify the expected request
            parameters as keyword arguments.
        :raises AssertionError: If no connection that matches the expectation was made.

.. function:: iter_side_effects(side_effects)

    Combine multiple endpoint side effects into one, so that each subsequent call uses the next side effect.

    :param side_effects: iterable of the side effects to combine.
    :type side_effects: :class:`~collections.abc.Iterable`

    :return: A function that can be used as an endpoint side effect.

    .. note::

        This function respects the special case of a side effect being a starlette response.

    .. warning::

        If there are less side effects than calls, a StopIteration will be raises within the handler. Which is why it
        is recommended to use :func:`itertools.cycle` to ensure that there are infinite side effects.

        .. code-block::
            :caption: Example of infinite side effects

            side_effect = iter_side_effects(itertools.chain(
                [
                    PlainTextResponse('hi'),
                    PlainTextResponse('hello'),
                    PlainTextResponse('how are you?'),
                ],
                itertools.cycle([PlainTextResponse('im tired now')])
            ))
            endpoint = server.add_http_endpoint('GET', '/', side_effect)
            assert get(server.local_url()+'/').text == 'hi'
            assert get(server.local_url()+'/').text == 'hello'
            assert get(server.local_url()+'/').text == 'how are you?'

            assert get(server.local_url()+'/').text == 'im tired now'
            assert get(server.local_url()+'/').text == 'im tired now'
            ...