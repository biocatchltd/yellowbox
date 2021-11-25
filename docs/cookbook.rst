Cookbook
=================


.. _Create-your-own-Yellow-service:

Create your own Yellow service
---------------------------------

If your service requires a service that isn't offered by the Yellowbox :ref:`extras <extras>`, you can easily create
your own. Let's for example create an Aerospike service. We'll use the `official Aerospike image
<https://hub.docker.com/_/aerospike>`_.

.. note:: Which superclass to use?

    * If your service requires only a single docker container, use :class:`~subclasses.SingleContainerService`.
    * If your service requires multiple docker containers, but outside clients will only ever interface with one of
      them, use :class:`~subclasses.SingleEndpointService`.
    * If your service requires multiple docker containers, and outside clients will be able to interface with more than
      one of them, use :class:`~subclasses.ContainerService`.

Since the Aerospike service is a single container, we'll use the :class:`~subclasses.SingleContainerService` superclass.
We'll also include the :class:`~subclasses.RunMixin` mixin, which will allow us to run the service like a context
manager.

.. code-block::

    from yellowbox.subclasses import SingleContainerService, RunMixin

    class AerospikeService(SingleContainerService, RunMixin):
        ...

Since the superclass requires a container, we'll create it in out initializer for the class. We can use Yellowbox's
utility function :func:`~containers.create_and_pull` to easily create the container from an image name, and pass that
container to the superclass initializer.

.. code-block::
    :emphasize-lines: 1, 5-8

    from yellowbox.containers import create_and_pull
    from yellowbox.subclasses import SingleContainerService, RunMixin

    class AerospikeService(SingleContainerService, RunMixin):
        def __init__(self, docker_client: DockerClient, image='aerospike:ce-5.7.0.8', **kwargs):
            container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
            # note that at this point, the container is CREATED, but not yet RUNNING
            super().__init__(container, **kwargs)

.. note::

    When you need to pull multiple images, you can use the :func:`~containers.SafeContainerCreator` function to ensure
    that they are pulled and created safely.

We'll also need to implement :class:`~sublasses.SingleContainerService`'s sing le abstract method
:meth:`~sublasses.SingleContainerService.start`. For now, we'll just delegate to ``super().start()``, which will
automatically start the container.

.. code-block::
    :emphasize-lines: 10-11

    from yellowbox.containers import create_and_pull
    from yellowbox.subclasses import SingleContainerService, RunMixin

    class AerospikeService(SingleContainerService, RunMixin):
        def __init__(self, docker_client: DockerClient, image='aerospike:ce-5.7.0.8', **kwargs):
            container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
            # note that at this point, the container is CREATED, but not yet RUNNING
            super().__init__(container, **kwargs)

        def start(self, retry_spec: Optional[RetrySpec] = None):
            return super().start(retry_spec)

We can actually start the service now! We can now run it like any other service (``with
AerospikeService.run(docker_client) as service``). But if we were to try to run it and attempt to connect to the
aerospike container from our docker host (assuming we somehow managed to get its connection info, more on that later),
we might run into an issue.

.. code-block::

    class AerospikeService(SingleContainerService, RunMixin):
        ...

    with docker_client() as dc:
    with AerospikeService.run(dc, remove=False) as aerospike_service:
        config = {
            'hosts': [('127.0.0.1', ...)]
        }
        client = aerospike.client(config).connect()  # <-- this will fail with a generic connection error

What's happening? Did the startup fail? Not Exactly. Consider that the above script will work if we change the start
method to be:

.. code-block::
    :emphasize-lines: 3

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start(retry_spec)
        sleep(10)
        return self

Docker can **start a container**, but we need to wait until it's startup is done before we can connect to it. If we
sleep for a while for the service to start up, then we'll be able to connect to it. In general,
:meth:`service.YellowService.start` should block until the underlying service's startup is complete.

Of course we don't want to actually sleep, we might sleep for too long and waste time, or worse, we might not sleep
enough, and still have connection issues. So instead. after we start the container, we'll continually attempt to connect
to the service until we succeed. In order to do this, we'll need to implement a way to connect to the service. Let's
start by adding a method that gets the connection info for the service. We can use the utility function
:func:`~containers.get_ports` to get the external ports a service exposes.

.. code-block::
    :emphasize-lines: 1, 4, 14-15

    from yellowbox.containers import create_and_pull, get_ports
    from yellowbox.subclasses import SingleContainerService, RunMixin

    INTERNAL_AEROSPOKE_PORT = 3000

    class AerospikeService(SingleContainerService, RunMixin):
        def __init__(self, docker_client: DockerClient, image='aerospike:ce-5.7.0.8', **kwargs):
            container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
            super().__init__(container, **kwargs)

        def start(self, retry_spec: Optional[RetrySpec] = None):
            return super().start(retry_spec)

        def client_port(self):
            return get_ports(self.container)[INTERNAL_AEROSPOKE_PORT]

Next, let's implement a method that returns an aerospike client connected to the service. (we can also use this method
when we test our app later, using it to either set the database before an application runs, or to query it after).

.. code-block::
    :emphasize-lines: 1, 19-23

    import aerospike

    from yellowbox.containers import create_and_pull, get_ports
    from yellowbox.subclasses import SingleContainerService, RunMixin

    INTERNAL_AEROSPOKE_PORT = 3000

    class AerospikeService(SingleContainerService, RunMixin):
        def __init__(self, docker_client: DockerClient, image='aerospike:ce-5.7.0.8', **kwargs):
            container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
            super().__init__(container, **kwargs)

        def start(self, retry_spec: Optional[RetrySpec] = None):
            return super().start(retry_spec)

        def client_port(self):
            return get_ports(self.container)[INTERNAL_AEROSPOKE_PORT]

        def client(self):
            config = {
                'hosts': [('127.0.0.1', self.client_port())]
            }
            return aerospike.client(config).connect()

Now we can use the ``client`` method to connect to the service, and to retry connecting to it until we succeed during
startup. to know how much we should retry, we can use the ``retry_spec`` argument (if it is ``None``, we should use some
sensible default, depending on how long we expect the startup to take).

.. code-block::
    :emphasize-lines: 14-16

    import aerospike

    from yellowbox.containers import create_and_pull, get_ports
    from yellowbox.subclasses import SingleContainerService, RunMixin

    INTERNAL_AEROSPOKE_PORT = 3000

    class AerospikeService(SingleContainerService, RunMixin):
        def __init__(self, docker_client: DockerClient, image='aerospike:ce-5.7.0.8', **kwargs):
            container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
            super().__init__(container, **kwargs)

        def start(self, retry_spec: Optional[RetrySpec] = None):
            super().start()
            retry_spec = retry_spec or RetrySpec(max_retries=10,retry_interval=1)
            retry_spec.retry(self.client, aerospike.exception.AerospikeError)
            return self

        def client_port(self):
            return get_ports(self.container)[INTERNAL_AEROSPOKE_PORT]

        def client(self):
            config = {
                'hosts': [('127.0.0.1', self.client_port())]
            }
            return aerospike.client(config).connect()

And we're done! We can now use the ``AerospikeService.run`` function to start the service, use the ``client``
method to connect to it from the host machine.

.. note:: Why is *retry_spec* customizable?

    For most machines, whatever sensible retry_spec is bundled as the service default will suffice. However since we're
    waiting for a machine that is containerized, this will not always be the case. On some machines the service will
    be virtualized, emulated, or even throttled (especially on older machines that don't support virtualization, or
    slower machines like CI/CD pipelines). In these cases, we may increase the retry_spec to a higher value, to afford
    the service more time to start up.

Creating an HTTP/Websocket service as a class
--------------------------------------------------

The :class:`yellowbox.extras.webserver.Webserver` class is a feature-complete HTTP/Websocket service. It can be used to
mock HTTP/Websocket dependencies to great effect by itself, but sometimes it's more convenient to subclass it to treat
your mocked server as a specialized class.

Consider for example a case where your application requires a connection to an HTTP server with an endpoint
``/api/v1/users``, that returns a JSON response.

.. code-block::
    :caption: example API response

    GET /api/v1/users HTTP/1.1
    {
        "users": [
            "Jerry",
            "Elaine",
            "George",
            ...
        ]
    }

Suppose we want to be able to easily change the response per test. We can implement this easily enough by combining
pytest fixtures and the ``Webserver`` class.

.. code-block::

    import pytest
    from starlette.responses import JSONResponse, Response
    from yellowbox.extras.webserver import Webserver, http_endpoint

    @pytest.fixture(scope='session')
    def user_service():
        with Webserver('user_service').start() as service:
            yield service

    @pytest.fixture(scope='session', autouse=True)
    def user_service_route(user_service):
        return user_service.add_http_route('GET', '/api/v1/users', JSONResponse({'users': ['user1', 'user2', 'user3']}))

    def test_normal(user_service):
        ... # perform a normal test here, expecting the user endpoint to return ['user1', 'user2', 'user3']

    def test_no_users(user_service_route):
        with user_service_route.patch(JSONResponse({'users': []}):
            ... # perform a test here, expecting the user endpoint to return an empty list

    def test_error(user_service_route):
        with user_service_route.patch(Response(status_code=500)):
            ... # perform a test here, expecting the user endpoint to return an error

    def test_gang(user_service_route):
        with user_service_route.patch(JSONResponse({'users': ['Charlie', 'Dennis', 'Frank', 'Dee', 'Mac']}):
            ... # perform a test here, expecting the user endpoint to return the above list

This will work perfectly fine, but we can already see some cracks in the design. For one, we need to use two fixture to
be able to patch the endpoint, and we'd need to add another fixture for every extra endpoint we'd like to test. And
second, we already needed to repeat the schema of the response every time we wanted to patch it, which isn't very DRY,
and will only get more complicated as our api gets more structured (what happens when we want to bundle user
permissions to our API?).

we can overcome both of these issues by using the ``Webserver`` class as a base class, and then subclassing it to create
a specialized class to handle our users.

.. code-block::

    from yellowbox.extras.webserver import Webserver

    class UserServer(Webserver):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.users = ['user1', 'user2', 'user3']

        def start(self):
            super().start()

            async def get_users(request):
                return JSONResponse({'users': self.users})

            self.users_endpoint = self.add_http_route('GET', '/api/v1/users', get_users)

            return self

Now we can use our new class in tests (in conjunction with the
`monkeypatch <https://docs.pytest.org/en/6.2.x/monkeypatch.html>`_ fixture to easily change attributes in tests):

.. code-block::

    import pytest
    from starlette.responses import Response

    @pytest.fixture(scope='session')
    def user_service():
        with UserServer('user_service').start() as service:
            yield service

    def test_normal(user_service):
        ... # perform a normal test here, expecting the user endpoint to return ['user1', 'user2', 'user3']

    def test_no_users(user_service, monkeypatch):
        monkeypatch.setattr(user_service, 'users', [])
        ... # perform a test here, expecting the user endpoint to return an empty list

    def test_error(user_service):
        with user_service.users_endpoint.patch(Response(status_code=500)):
            ... # perform a test here, expecting the user endpoint to return an error

    def test_gang(user_service, monkeypatch):
        monkeypatch.setattr(user_service, 'users', ['Charlie', 'Dennis', 'Frank', 'Dee', 'Mac'])
        ... # perform a test here, expecting the user endpoint to return the above list

That's much better! But our subclass implementation is still far from perfect. It will fail type linters, and the
declaration of routes that use self as a closure var may seem bulky to some. We can simplify all this be using the
`class_http_endpoint` decorator, which will automatically create a route for us when we start a subclass instance.

.. code-block::
    :emphasize-lines: 6-11

    import pytest
    from unittest.mock import patch
    from starlette.responses import Response
    from yellowbox.extras.webserver import Webserver, class_http_endpoint

    class UserServer(Webserver):
        users = ['user1', 'user2', 'user3']

        @class_http_endpoint('GET', '/api/v1/users')
        async def users_endpoint(self, request):
            return JSONResponse({'users': self.users})

    @pytest.fixture(scope='session')
    def user_service():
        with UserServer('user_service').start() as service:
            yield service

    def test_normal(user_service):
        ... # perform a normal test here, expecting the user endpoint to return ['user1', 'user2', 'user3']

    def test_no_users(user_service, monkeypatch):
        monkeypatch.setattr(user_service, 'users', [])
        ... # perform a test here, expecting the user endpoint to return an empty list

    def test_error(user_service):
        with user_service.users_endpoint.patch(Response(status_code=500)):
            ... # perform a test here, expecting the user endpoint to return an error

    def test_gang(user_service, monkeypatch):
        monkeypatch.setattr(user_service, 'users', ['Charlie', 'Dennis', 'Frank', 'Dee', 'Mac'])
        ... # perform a test here, expecting the user endpoint to return the above list