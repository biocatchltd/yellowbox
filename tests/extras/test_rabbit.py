from time import sleep

from pika import BlockingConnection
from pytest import mark


from yellowbox.extras.rabbit_mq import RabbitMQService, RABBIT_HTTP_API_PORT
@mark.parametrize('spinner', [True, False])
def test_make_rabbit(docker_client, spinner):
    with RabbitMQService.run(docker_client, spinner=spinner):
        pass

@mark.parametrize('tag', ['management-alpine', 'latest'])
def test_connection_works(docker_client, tag):
    with RabbitMQService.run(docker_client, image="rabbitmq:management-alpine") as rabbit:
        connection: BlockingConnection
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')

            channel.basic_publish('', 'routing', body=b'hi there')
            sleep(1)
            *_, body = channel.basic_get('routing', auto_ack=True)
            assert body == b'hi there'


def test_connection_works_sibling_network(docker_client):
    with YellowNetwork.create(docker_client) as network:
        with YellowRabbitMq.run(docker_client, tag="management-alpine") as rabbit, \
                network.connect(rabbit) as aliases:
            url = f"http://{aliases[0]}:{RABBIT_HTTP_API_PORT}/api/vhosts"
            container = docker_client.containers.create(
                "byrnedo/alpine-curl", f'-u guest:guest -vvv -I "{url}" --http0.9',
                detach=True
            )
            with network.connect(container):
                container.start()
                return_status = container.wait()
                assert return_status["StatusCode"] == 0


def test_connection_works_sibling(docker_client):
    with YellowRabbitMq.run(docker_client, tag="management-alpine") as rabbit:
        api_port = rabbit.get_exposed_ports()[RABBIT_HTTP_API_PORT]
        url = f"http://host.docker.internal:{api_port}/api/vhosts"
        container = docker_client.containers.create(
            "byrnedo/alpine-curl", f'-u guest:guest -vvv -I "{url}" --http0.9',
            detach=True
        )
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0
