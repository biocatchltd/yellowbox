from contextlib import contextmanager
from typing import ContextManager

from docker import DockerClient
from redis import Redis, ConnectionError as RedisConnectionError

from yellowbox.context_managers import get_spinner, killing
from yellowbox.utils import retry
from yellowbox.service import YellowContainer

REDIS_DEFAULT_PORT = 6379


class YellowRedis(YellowContainer):
    def client_port(self):
        return self.get_exposed_ports()[REDIS_DEFAULT_PORT]

    def client(self, connection_cls=Redis):
        port = self.client_port()
        return connection_cls(host='localhost', port=port)

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True) -> ContextManager['YellowRedis']:
        spinner = get_spinner(spinner)
        with spinner("Fetching redis..."):
            container = docker_client.containers.run(f"redis:{tag}", detach=True, publish_all_ports=True)

        with killing(container, signal='SIGTERM'):
            self = cls(container)
            with self.client() as client:
                # Attempt pinging redis until it's up and running
                with spinner("Waiting for redis to start..."):
                    retry(client.ping, RedisConnectionError)

            yield self
