from contextlib import contextmanager
from typing import Type, TypeVar

from docker import DockerClient
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.exceptions import AMQPConnectionError

from yellowbox.containers import get_ports
from yellowbox.service import SingleContainerService
from yellowbox.utils import _get_spinner, retry

RABBIT_DEFAULT_PORT = 5672

_T = TypeVar("_T")


# TODO: Eliminate repeated argument defaults. Consts?
class RabbitMQService(SingleContainerService):
    def __init__(self, container, *, user="guest", password="guest",
                 virtual_host="/", _auto_remove=False):
        self.container = container
        self.user = user
        self.password = password
        self.virtual_host = virtual_host

    def connection_port(self):
        return get_ports(self.container)[RABBIT_DEFAULT_PORT]

    def connection(self):
        credentials = PlainCredentials(self.user, self.password)
        connection_params = ConnectionParameters(
            'localhost', self.connection_port(),
            credentials=credentials, virtual_host=self.virtual_host)
        return BlockingConnection(connection_params)

    @classmethod
    def from_docker(cls, docker_client: DockerClient, tag='rabbitmq:latest', *,
                    user="guest", password="guest", virtual_host="/"):
        container = docker_client.containers.create(
            tag, publish_all_ports=True, detach=True, environment={
                'RABBITMQ_DEFAULT_USER': user,
                'RABBITMQ_DEFAULT_PASS': password,
                'RABBITMQ_DEFAULT_VHOST': virtual_host
            })
        return cls(container, _auto_remove=True)

    @classmethod
    @contextmanager
    def run(cls: Type[_T], docker_client: DockerClient, tag='rabbitmq:latest', *, spinner=True,
            user="guest", password="guest", virtual_host="/") -> _T:
        spinner = _get_spinner(spinner)
        with spinner("Fetching rabbitmq..."):
            service = cls.from_docker(docker_client, tag=tag, user=user,
                                      password=password, virtual_host=virtual_host)

        with spinner("Waiting for rabbitmq to start..."), service.start():
            conn = retry(service.connection, AMQPConnectionError)
            conn.close()
            yield service
