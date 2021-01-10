from time import sleep

import pytest
from pika import BlockingConnection
import requests
from pytest import mark, raises

from yellowbox.containers import get_ports
from yellowbox.extras.rabbit_mq import RabbitMQService, RABBIT_HTTP_API_PORT
from yellowbox.networks import temp_network, connect


@mark.parametrize('spinner', [True, False])
def test_make_rabbit(docker_client, spinner):
    with RabbitMQService.run(docker_client, spinner=spinner):
        pass


@mark.parametrize('tag', ['rabbitmq:management-alpine', 'rabbitmq:latest'])
@mark.parametrize('vhost', ["/", "guest-vhost"])
def test_connection_works(docker_client, tag, vhost):
    with RabbitMQService.run(docker_client, image=tag, virtual_host=vhost) as rabbit:
        connection: BlockingConnection
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')

            channel.basic_publish('', 'routing', body=b'hi there')
            sleep(1)
            *_, body = channel.basic_get('routing', auto_ack=True)
            assert body == b'hi there'


@mark.parametrize('vhost', ["/", "guest-vhost"])
def test_connection_works_sibling_network(docker_client, vhost, create_and_pull):
    with temp_network(docker_client) as network:
        with RabbitMQService.run(docker_client, image="rabbitmq:management-alpine", virtual_host=vhost) \
                as rabbit, \
                connect(network, rabbit) as aliases:
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


@mark.parametrize('vhost', ["/", "guest-vhost"])
def test_connection_works_sibling(docker_client, host_ip, vhost, create_and_pull):
    with RabbitMQService.run(docker_client, image="rabbitmq:management-alpine", virtual_host=vhost) \
            as rabbit:
        api_port = get_ports(rabbit.container)[RABBIT_HTTP_API_PORT]
        url = f"http://{host_ip}:{api_port}/api/vhosts"
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
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get(rabbit.management_url(), auth=(rabbit.user, rabbit.password))
        rabbit.enable_management()
        requests.get(rabbit.management_url()).raise_for_status()


def assert_no_queues(rabbit: RabbitMQService):
    url = rabbit.management_url() + "api/queues"
    response = requests.get(url, auth=(rabbit.user, rabbit.password))
    assert not response.json()


def test_reset_state(docker_client):
    with RabbitMQService.run(docker_client, enable_management=True) as rabbit:
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')
            channel.basic_consume('routing', lambda: 1 / 0)  # no-op
        rabbit.reset_state()
        assert_no_queues(rabbit)


def test_reset_state_bad(docker_client):
    with RabbitMQService.run(docker_client, enable_management=True) as rabbit:
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')
            channel.basic_consume('routing', lambda: 1 / 0)  # no-op
            with raises(requests.HTTPError):
                rabbit.reset_state()


def test_reset_state_force(docker_client):
    with RabbitMQService.run(docker_client, enable_management=True) as rabbit:
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')
            channel.basic_consume('routing', lambda: 1 / 0)  # no-op
            rabbit.reset_state(force_queue_deletion=True)
            assert_no_queues(rabbit)
