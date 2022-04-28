import itertools
from time import sleep

import requests
from pika import BlockingConnection
from pytest import mark, raises, fixture

from tests.util import unique_name_generator
from yellowbox.containers import get_ports
from yellowbox.extras.rabbit_mq import RABBIT_HTTP_API_PORT, RabbitMQService
from yellowbox.networks import connect, temp_network
from yellowbox.utils import docker_host_name


@mark.parametrize('spinner', [True, False])
def test_make_rabbit(docker_client, spinner):
    with RabbitMQService.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_connection_works_async(docker_client):
    async with RabbitMQService.arun(docker_client) as rabbit:
        connection: BlockingConnection
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')

            channel.basic_publish('', 'routing', body=b'hi there')
            sleep(1)
            *_, body = channel.basic_get('routing', auto_ack=True)
            assert body == b'hi there'


@fixture(scope='module',
         params=itertools.product(['rabbitmq:management-alpine', 'rabbitmq:latest'], ['/', "guest-vhost"]))
def rabbit(docker_client, request):
    tag, vhost = request.param
    with RabbitMQService.run(docker_client, image=tag, virtual_host=vhost, spinner=False,
                             enable_management=True) as service:
        yield service


q_name = fixture(unique_name_generator())


def test_connection_works(docker_client, rabbit, q_name):
    connection: BlockingConnection
    with rabbit.connection() as connection:
        channel = connection.channel()
        channel.queue_declare(q_name)

        channel.basic_publish('', q_name, body=b'hi there')
        sleep(1)
        *_, body = channel.basic_get(q_name, auto_ack=True)
        assert body == b'hi there'


def test_connection_works_sibling_network(docker_client, rabbit, create_and_pull):
    with temp_network(docker_client) as network, connect(network, rabbit) as aliases:
        url = f"http://{aliases[0]}:{RABBIT_HTTP_API_PORT}/api/vhosts"
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest", f'-u guest:guest -vvv -I "{url}" --http0.9',
            detach=True
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_connection_works_sibling(docker_client, rabbit, create_and_pull):
    api_port = get_ports(rabbit.container)[RABBIT_HTTP_API_PORT]
    url = f"http://{docker_host_name}:{api_port}/api/vhosts"
    container = create_and_pull(
        docker_client,
        "byrnedo/alpine-curl:latest", f'-u guest:guest -vvv -I "{url}" --http0.9',
        detach=True
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0


def test_management_enabling(docker_client):
    with RabbitMQService.run(docker_client) as rabbit:
        with raises(requests.exceptions.ConnectionError):
            requests.get(rabbit.management_url(), auth=(rabbit.user, rabbit.password))
        rabbit.enable_management()
        requests.get(rabbit.management_url()).raise_for_status()


def assert_no_queues(rabbit: RabbitMQService):
    url = rabbit.management_url() + "api/queues"
    response = requests.get(url, auth=(rabbit.user, rabbit.password))
    assert not response.json()


def test_reset_state(docker_client, rabbit, q_name):
    with rabbit.connection() as connection:
        channel = connection.channel()
        channel.queue_declare(q_name)
        channel.basic_consume(q_name, lambda: 1 / 0)  # no-op
    rabbit.reset_state()
    assert_no_queues(rabbit)


def test_reset_state_bad(docker_client, rabbit, q_name):
    with rabbit.connection() as connection:
        channel = connection.channel()
        channel.queue_declare(q_name)
        channel.basic_consume(q_name, lambda: 1 / 0)  # no-op
        with raises(requests.HTTPError):
            rabbit.reset_state()


def test_reset_state_force(docker_client, rabbit, q_name):
    with rabbit.connection() as connection:
        channel = connection.channel()
        channel.queue_declare(q_name)
        channel.basic_consume(q_name, lambda: 1 / 0)  # no-op
        rabbit.reset_state(force_queue_deletion=True)
        assert_no_queues(rabbit)
