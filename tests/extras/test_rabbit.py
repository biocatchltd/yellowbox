from time import sleep

from pika import BlockingConnection
from pytest import mark

from yellowbox.extras import RabbitMQService


@mark.parametrize('spinner', [True, False])
def test_make_redis(docker_client, spinner):
    with RabbitMQService.run(docker_client, spinner=spinner):
        pass


def test_connection_works(docker_client):
    with RabbitMQService.run(docker_client) as rabbit:
        connection: BlockingConnection
        with rabbit.connection() as connection:
            channel = connection.channel()
            channel.queue_declare('routing')

            channel.basic_publish('', 'routing', body=b'hi there')
            sleep(1)
            *_, body = channel.basic_get('routing', auto_ack=True)
            assert body == b'hi there'

def test_connection_works_sideload(docker_client):
    with RabbitMQService.run(docker_client) as rabbit:
        pass  # todo finish