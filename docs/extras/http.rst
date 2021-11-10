:mod:`extras.http_server` --- Simple HTTP Server
================================================

.. module:: extras.http_server
    :synopsis: Simple HTTP Server.

-------

An HTTP :class:`~service.YellowService` used to easily mock and test HTTP
connections.

.. deprecated:: 0.6.6
    Use :class:`~extras.http_server.webserver` instead.


.. class:: HttpService(host="0.0.0.0", port=0, name=None)

    A Simple HTTP server wrapped as :class:`~service.YellowService`.

    Inherits from :class:`~service.YellowService`.

    :param str host: is the listening host. Defaults to ``"0.0.0.0"`` to listen on all IPv4
     interfaces.
    :param int port: is the listening port. Defaults to ``0`` to let the OS choose a free port. Use :attr:`server_port` to fetch the port.
    :param Optional[str] name: is a string identifying this server and thread for logging purposes. If ``None``, a default name with a running number is generated.


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

    Has the following additional methods:

    .. method:: server_port
        :property:

        HTTP Server listening port.

    .. method:: local_url
        :property:

        Full URL to access the HTTP Server from localhost (including port).

    .. method:: container_url
        :property:

        Full URL to access the HTTP Server from inside a locally-running
        container (including port).

    .. method:: patch_route(method, route, side_effect=..., name=None)

        Create a context manager that temporarily adds a route handler to the
        service.

        *method* is the request method to add the route to.

        *route* is the route to attach the side effect to. All routes must begin
        with a slash "/".  Alternatively, The route may be a regex
        :class:`Pattern <re.compile>`, in which case the request path must fully
        match it. The match object is then stored in
        :meth:`RouterHTTPRequestHandler.match`, to be used by a side-effect
        callable.

        *side_effect* is the callback or result to return for the route. Accepts
        any of the following types:

        * int: to return the value as the HTTP status code, without a body.
        * bytes: to return 200, with the value as the response body.
        * str: invalid if the value is non-ascii, return 200 with the value,
        translated to bytes, as the response body.
        * callable: Must accept a :class:`RouterHTTPRequestHandler`. May return
        any of the above types, or None to handle the response directly with the
        :class:`RouterHTTPRequestHandler`.

        If *side_effect* is not specified, this method can be used as a
        decorator.

        Returns a context manager that will enable the route upon entry and
        disable it upon exit.

.. class:: RouterHTTPRequestHandler

        Inherits from :class:`http.server.BaseHTTPRequestHandler` and adds the
        following utility methods:

    .. method:: body()

        Return the body of the request as bytes, or ``None`` if it's empty.

    .. method:: path_params(**kwargs)

        Extract parameters from the query string.

        *kwargs* are forwarded to :func:`~urllib.parse.parse_qs`.

        Returns a mapping between parameter name and a list of the values
        provided.



