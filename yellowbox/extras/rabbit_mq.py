from contextlib import contextmanager
from typing import ContextManager

from docker import DockerClient
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.exceptions import AMQPConnectionError

from yellowbox.context_managers import get_spinner, killing
from yellowbox.utils import retry
from yellowbox.service import YellowContainer

RABBIT_DEFAULT_PORT = 5672
RABBIT_HTTP_API_PORT = 15672


class YellowRabbitMq(YellowContainer):
    def __init__(self, container, user, password, vhost):
        super().__init__(container)
        self.user = user
        self.password = password
        self.vhost = vhost

    def connection_port(self):
        return self.get_exposed_ports()[RABBIT_DEFAULT_PORT]

    def connection(self):
        credentials = PlainCredentials(self.user, self.password)
        connection_params = ConnectionParameters('localhost', self.connection_port(), credentials=credentials,
                                                 virtual_host=self.vhost)
        return BlockingConnection(connection_params)

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True,
            user="guest", password="guest", vhost_name="vhost") -> ContextManager['YellowRabbitMq']:
        spinner = get_spinner(spinner)
        with spinner("Fetching rabbitmq..."):
            container = docker_client.containers.run(f"rabbitmq:{tag}", detach=True, publish_all_ports=True,
                                                     environment={
                                                         'RABBITMQ_DEFAULT_USER': user,
                                                         'RABBITMQ_DEFAULT_PASS': password,
                                                         'RABBITMQ_DEFAULT_VHOST': vhost_name
                                                     })

        with killing(container, signal='SIGTERM'):
            self = cls(container, user, password, vhost_name)
            # Attempt pinging redis until it's up and running
            with spinner("Waiting for rabbitmq to start..."):
                with retry(self.connection, AMQPConnectionError):
                    pass

            yield self
