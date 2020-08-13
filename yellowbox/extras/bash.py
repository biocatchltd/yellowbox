from contextlib import contextmanager

from docker import DockerClient

from yellowbox.context_managers import get_spinner, killing
from yellowbox.service import YellowContainer

REDIS_DEFAULT_PORT = 6379


class YellowRedis(YellowContainer):
    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True) -> 'YellowRedis':
        spinner = get_spinner(spinner)
        with spinner("Fetching Redis..."):
            container = docker_client.containers.run(f"bash:{tag}", detach=True, publish_all_ports=True)

        with killing(container, signal='SIGTERM'):
            self = cls(container)
            yield self
