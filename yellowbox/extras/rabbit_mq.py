from contextlib import contextmanager
from typing import ContextManager, Optional
from urllib.parse import quote

import requests
from docker import DockerClient
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
from pika.exceptions import AMQPConnectionError

from yellowbox.containers import create_and_pull, get_ports, upload_file
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import RunMixin, SingleContainerService

__all__ = ['RabbitMQService', 'RABBIT_DEFAULT_PORT', 'RABBIT_HTTP_API_PORT']

RABBIT_DEFAULT_PORT = 5672
RABBIT_HTTP_API_PORT = 15672


class RabbitMQService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='rabbitmq:latest', *, user="guest", password="guest",
                 virtual_host="/", **kwargs):
        self.user = user
        self.password = password
        self.virtual_host = virtual_host
        super().__init__(create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True,
            ports={RABBIT_HTTP_API_PORT: 0},  # Forward management port by default.
        ), **kwargs)

        upload_file(self.container, '/etc/rabbitmq/rabbitmq.conf',
                    f'''
                    default_pass = {password}
                    default_user = {user}
                    default_vhost = {virtual_host}
                    loopback_users = none
                    '''.encode())

    def connection_port(self):
        return get_ports(self.container)[RABBIT_DEFAULT_PORT]

    def connection(self, **kwargs):
        credentials = PlainCredentials(self.user, self.password)
        connection_params = ConnectionParameters(
            'localhost', self.connection_port(),
            credentials=credentials, virtual_host=self.virtual_host,
            **kwargs
        )
        return BlockingConnection(connection_params)

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=30)
        conn = retry_spec.retry(self.connection, (AMQPConnectionError, ConnectionError))
        conn.close()
        return self

    def management_url(self):
        try:
            return f"http://localhost:{get_ports(self.container)[RABBIT_HTTP_API_PORT]}/"
        except KeyError as exc:
            raise RuntimeError("Management is not enabled.") from exc

    def enable_management(self):
        if not self.is_alive():
            raise RuntimeError("Must be used on an already-running container.")

        if RABBIT_HTTP_API_PORT not in get_ports(self.container):
            raise RuntimeError("Container must have the management port exposed.")

        self.container.exec_run("rabbitmq-plugins enable rabbitmq_management")

    def reset_state(self, force_queue_deletion=False):
        try:
            management_url = self.management_url()
        except RuntimeError as e:
            raise RuntimeError('management must be enabled for clean_slate') from e

        queues_url = management_url + 'api/queues'
        replies = requests.get(queues_url, auth=(self.user, self.password))
        replies.raise_for_status()
        extant_queues = replies.json()
        delete_params = {}
        if not force_queue_deletion:
            delete_params['if-unused'] = 'true'
        for queue in extant_queues:
            name = quote(queue['name'], safe='')
            vhost = quote(queue['vhost'], safe='')
            requests.delete(
                management_url + f'api/queues/{vhost}/{name}',
                auth=(self.user, self.password), params=delete_params
            ).raise_for_status()

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, *, enable_management=False, **kwargs):
        cmg: ContextManager[RabbitMQService] = super().run(docker_client, **kwargs)
        with cmg as ret:
            if enable_management:
                ret.enable_management()
            yield ret

    def stop(self, signal='SIGKILL'):
        # change in default
        return super().stop(signal)
