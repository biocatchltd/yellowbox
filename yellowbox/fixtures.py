def _ok(spinner):
    spinner.ok("✅ ")

def _fail(spinner):
    spinner.fail("💥 ")

@contextmanager
def _spinner(text):
    with yaspin(text=text) as spinner:
        try:
            yield
        except Exception:
            _fail(spinner)
            raise
        _ok(spinner)


def _run_container(docker_client, *args, detach=True,
                   publish_all_ports=True, remove=True, **kwargs) -> DockerContainer:
    """Convenience function to run containers"""
    return docker_client.containers.run(
        *args, detach=detach, publish_all_ports=publish_all_ports, remove=remove, **kwargs)

@fixture(scope="session")
def docker_client() -> DockerClient:
    client = DockerClient.from_env()
    client.ping()  # Make sure we're actually connected.
    with closing(client):
        yield client


@fixture(scope="session")
def redis(docker_client) -> DockerContainer:
    with _spinner("Fetching Redis..."):
        container = _run_container(docker_client, "redis:latest")

    with terminating(container):
        container.reload()
        redis_port = get_ports(container)[REDIS_DEFAULT_PORT]
        # Attempt pinging redis until it's up and running
        redis = Redis(host="localhost", port=redis_port)
        with _spinner("Waiting for Redis to start..."):
            assert retry(
                redis.ping, RedisConnectionError), "Failed connecting to Redis."

        yield container


@fixture(scope="session")
def rabbitmq(docker_client) -> DockerContainer:
    with _spinner("Fetching RabbitMQ..."):
        container = _run_container(docker_client, "rabbitmq:latest",
                                   ports={RABBIT_DEFAULT_PORT: RABBIT_DEFAULT_PORT})

    with terminating(container):
        container.reload()
        rabbit_port = get_ports(container)[RABBIT_DEFAULT_PORT]

        connection_params = ConnectionParameters(
            "localhost", rabbit_port,
            credentials=PlainCredentials(RABBIT_USER, RABBIT_PASSWORD))

        def ping():
            assert BlockingConnection(connection_params).is_open

        with _spinner("Waiting for RabbitMQ to start..."):
            # Make sure rabbit is up.
            retry(ping, AMQPConnectionError)

        yield rabbitmq


@fixture(scope="session")
def logstash(docker_client):
    with _spinner("Fetching Logstash..."):
        container = _run_container(docker_client, "logstash:7.8.1",
                                   ports={LOGSTASH_DEFAULT_PORT: None})

    with terminating(container):
        container.reload()
        yield container
