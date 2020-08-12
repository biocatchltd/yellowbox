from contextlib import contextmanager

from docker import DockerClient
from redis import Redis, ConnectionError as RedisConnectionError

from yellowbox.context_managers import get_spinner, terminating
from yellowbox.utils import retry
from yellowbox.yellow import YellowContainer

REDIS_DEFAULT_PORT = 6379


class YellowRedis(YellowContainer):
    def client(self, connection_cls=Redis):
        port = self.get_ports()[REDIS_DEFAULT_PORT]
        return connection_cls(host='localhost', port=port)

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True) -> 'YellowRedis':
        spinner = get_spinner(spinner)
        with spinner("Fetching Redis..."):
            container = docker_client.containers.run(f"redis:{tag}", detach=True, publish_all_ports=True)

        with terminating(container):
            self = cls(container)
            with self.client() as client:
                # Attempt pinging redis until it's up and running
                with spinner("Waiting for Redis to start..."):
                    retry(client.ping, RedisConnectionError)

            yield self
