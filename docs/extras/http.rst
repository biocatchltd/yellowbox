:mod:`extras.http_server` --- Simple HTTP Server
================================================

.. module:: extras.http_server
    :synopsis: Simple HTTP Server.

-------

An HTTP :class:`~service.YellowService` used to easily mock and test HTTP
connections.

.. deprecated:: 0.6.6
    Use :class:`~extras.http_server.webserver` instead.

.. code-block::
    :caption: Example Usage

    with HttpService().start() as service:
      @service.patch_route('GET', '/hello/world')
      def hello_world(handler: RouterHTTPRequestHandler):
         return "hi there"
      # hello_world is now a context manager
      with hello_world:
         # within this scope, the path "/hello/world" will return a 200 response
         # with the body "hi there"
         assert requests.get(service.local_url+"/hello/world").text == "hi there"
      # routes can also be set without a function
      with service.patch_route('GET', '/meaning_of_life', '42'):
         assert requests.get(service.local_url+"/meaning_of_life").content == b'42'

.. class:: HttpService(host="0.0.0.0", port=0, name=None)

    A Simple HTTP server wrapped as :class:`~service.YellowService`.

    Inherits from :class:`~service.YellowService`.

    :param str host: is the listening host. Defaults to ``"0.0.0.0"`` to listen on all IPv4
     interfaces.
    :param int port: is the listening port. Defaults to ``0`` to let the OS choose a free port. Use :attr:`server_port`
     to fetch the port.
    :param Optional[str] name: is a string identifying this server and thread for logging purposes. If ``None``, a
     default name with a running number is generated.

    .. property:: server_port
        :type: int

        HTTP Server listening port.

    .. property:: local_url
        :type: str

        Full URL to access the HTTP Server from localhost (including port).

    .. property:: container_url
        :type: str

        Full URL to access the HTTP Server from inside a locally-running
        container (including port).

    .. method:: patch_route(method, route, side_effect=..., name=None)

        Create a context manager that temporarily adds a route handler to the
        service.

        :param str method: The request method to add the route to.

        :param route: The route to attach the side effect to. All routes must begin with a slash ``/``.  Alternatively,
         The route may be a compiled regex pattern, in which case the request path must fully match it. The match object
         is then stored in :attr:`RouterHTTPRequestHandler.match`, to be used by a side-effect callable.
        :type route: :class:`str` | :class:`~typing.Pattern`\[:class:`str`]

        :param side_effect: The result of the route if requested, or a callback to return the result. Accepts following
         types:

         * :class:`int`: to return the value as the HTTP status code, without a body.
         * :class:`bytes`: to return 200, with the value as the response body.
         * :class:`str`: invalid if the value is non-ascii, return 200 with the value, translated to bytes, as the
           response body.
         * :class:`~collections.abc.Callable`: A callback that accepts a :class:`RouterHTTPRequestHandler`
           positional argument. Should return any of the above values for similar effects. Alternatively, the callback
           can return the handler itself to indicate that the callback handled the response on its own and no further
           actions are needed.

         If *side_effect* is not specified, this method can be used as a decorator.

        :type side_effect: :class:`int` | :class:`bytes` | :class:`str` | :class:`~collections.abc.Callable`

        :return: A context manager that will add the route to the service upon entry, and remove it upon exit.

.. class:: RouterHTTPRequestHandler

        Inherits from :class:`http.server.BaseHTTPRequestHandler` and adds the
        following utility methods:

    .. attribute:: match
        :type: typing.Match[str] | True

        If the route has a regular expression path, the match of the path to route's pattern will be stored here. If
        the path is a string, will be ``True``.

    .. method:: body()-> bytes | None

        Return the body of the request as bytes, or ``None`` if it's empty.

    .. method:: path_params(**kwargs)

        Extract parameters from the query string.

        :params kwargs: Forwarded to :func:`~urllib.parse.parse_qs`.

        :returns: A mapping between parameter name and a list of the values provided in the query.
        :rtype: :class:`~collections.abc.Mapping`\[:class:`str`, :class:`list`\[:class:`str`\]]

    .. method:: parse_url() -> urllib.parse.ParseResult

        Parse the request URL into a :class:`~urllib.parse.ParseResult` object.



