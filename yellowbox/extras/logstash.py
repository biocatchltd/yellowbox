from contextlib import contextmanager
from typing import ContextManager

from docker import DockerClient

from yellowbox.context_managers import get_spinner, killing
from yellowbox.service import YellowContainer

LOGSTASH_DEFAULT_PORT = 5959


class YellowLogstash(YellowContainer):
    def client_port(self):
        return self.get_exposed_ports()[LOGSTASH_DEFAULT_PORT]

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag, spinner=True) -> ContextManager['YellowLogstash']:
        spinner = get_spinner(spinner)
        with spinner("Fetching logstash..."):
            container = docker_client.containers.run(f"logstash:{tag}", detach=True, publish_all_ports=True)

        with killing(container, signal='SIGTERM'):
            yield cls(container)
