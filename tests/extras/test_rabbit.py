from time import sleep

from pika import BlockingConnection
from pytest import mark

from yellowbox.containers import get_ports, create_and_pull
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
def test_connection_works_sibling_network(docker_client, vhost):
    with temp_network(docker_client) as network:
        with RabbitMQService.run(docker_client, image="rabbitmq:management-alpine", virtual_host=vhost) as rabbit, \
                connect(network, rabbit) as aliases:
            url = f"http://{aliases[0]}:{RABBIT_HTTP_API_PORT}/api/vhosts"
            container = create_and_pull(
                docker_client,
                "byrnedo/alpine-curl", f'-u guest:guest -vvv -I "{url}" --http0.9',
                detach=True
            )
            with connect(network, container):
                container.start()
                return_status = container.wait()
                assert return_status["StatusCode"] == 0


@mark.parametrize('vhost', ["/", "guest-vhost"])
def test_connection_works_sibling(docker_client, host_ip, vhost):
    with RabbitMQService.run(docker_client, image="rabbitmq:management-alpine", virtual_host=vhost) as rabbit:
        api_port = get_ports(rabbit.container)[RABBIT_HTTP_API_PORT]
        url = f"http://{host_ip}:{api_port}/api/vhosts"
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl", f'-u guest:guest -vvv -I "{url}" --http0.9',
            detach=True
        )
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0
