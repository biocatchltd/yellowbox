Intro
-----------

Yellowbox is a library for making it easy to `blackbox-test <https://en.wikipedia.org/wiki/Black-box_testing>`_ your
code by setting up all the dependencies your program would need. Say your program requires connection to a redis
database, a postgresql database, and an HTTP server. You can use yellowbox to set up all of these dependencies for you.

.. code-block::

    from yellowbox import docker_client
    from yellowbox.extras.redis import RedisService
    from yellowbox.extras.postgresql import PostgreSQLService
    from yellowbox.extras.webserver import WebServer

    from starlette.responses import PlainTextResponse

    # Create a new docker client
    with docker_client() as client,\  # get a client to interface with docker
        RedisService.run(client) as redis,\  # start a redis docker container
        PostgreSQLService.run(client) as postgres,\  # start a postgresql docker container
        Webserver("math-service").start() as math_server:  # start a local HTTP server

        # Add a constant route to the webserver
        math_server.add_http_route('GET', '/api/v1/pi', PlainTextResponse("3.1415"))

        # now your app can be started with all the dependencies it needs
        app = MyApp(redis_url = 'localhost', redis_port = redis.client_port(),
                    postgres_conn_string = postgres.local_connection_string(),
                    math = math_server.local_url())


        app.run()

Yellowbox can be used seamlessly with `pytest <https://docs.pytest.org/>`_ fixtures

.. code-block::

    from pytest import fixture

    from yellowbox import docker_client as _docker_client
    from yellowbox.extras.redis import RedisService
    from yellowbox.extras.postgresql import PostgreSQLService
    from yellowbox.extras.webserver import WebServer

    from starlette.responses import PlainTextResponse

    # docker_client is a fixture automatically added by yellowbox

    @fixture(scope='session')
    def redis(docker_client):
        with RedisService.run(docker_client) as redis:
            yield redis

    @fixture(scope='session')
    def postgresql(docker_client):
        with PostgreSQLService.run(docker_client) as postgres:
            yield postgres

    @fixture(scope='session')
    def math_server():
        with Webserver("math-service").start() as math_server:
            math_server.add_http_route('GET', '/api/v1/pi', PlainTextResponse("3.1415"))
            yield math_server


    @fixture
    def app(redis, postgres, math_server):
        app = MyApp(redis_url = 'localhost', redis_port = redis.client_port(),
                    postgres_conn_string = postgres.local_connection_string(),
                    math = math_server.local_url())
        return app

    # you can now use the "app" fixture in your tests and get a fully-functional application

Yellowbox comes with built-in services for many popular infras, such as PostgreSQL, Redis, and RabbitMQ, and also has a
comprehensive, easy-to-use library to :ref:`create your own services <Create-your-own-Yellow-service>` for
whatever your app needs.

**Use Yellowbox if:**

* Your program requires other services to be running, such as a database, a webserver, a message queue, or a message
  broker.
* You want to test your program's ability to connect to these services.
* You want to test your program's connection to these services.
* You want the tests to easily integrate with your existing testing infrastructure. Making it easy to run these tests
  both locally and remotely in CI/CD.
