from typing import TypeVar

from docker import DockerClient
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.exceptions import AMQPConnectionError

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.service import ContainerService
from yellowbox.utils import retry

RABBIT_DEFAULT_PORT = 5672
RABBIT_HTTP_API_PORT = 15672

_T = TypeVar("_T")


# TODO: Eliminate repeated argument defaults. Consts?
class RabbitMQService(ContainerService):
    def __init__(self, containers, remove, kwargs):
        super().__init__(containers=containers, remove=remove, kwargs=kwargs)
        self.user = kwargs.get('user', 'guest')
        self.password = kwargs.get('password', 'guest')
        self.virtual_host = kwargs.get('virtual_host', '/')

    @property
    def container(self):
        return next(iter(self.containers))

    def connection_port(self):
        return get_ports(self.container)[RABBIT_DEFAULT_PORT]

    def connection(self):
        credentials = PlainCredentials(self.user, self.password)
        connection_params = ConnectionParameters(
            'localhost', self.connection_port(),
            credentials=credentials, virtual_host=self.virtual_host
        )
        return BlockingConnection(connection_params)

    def start(self):
        super().start()
        conn = retry(self.connection, AMQPConnectionError)
        conn.close()
        return self

    @classmethod
    def _make_containers(cls, docker_client: DockerClient, image='rabbitmq:latest', *, user="guest", password="guest",
                    virtual_host="/"):
        yield create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True, environment={
                'RABBITMQ_DEFAULT_USER': user,
                'RABBITMQ_DEFAULT_PASS': password,
                'RABBITMQ_DEFAULT_VHOST': virtual_host
            })

    def _endpoint_containers(self):
        return self.containers
