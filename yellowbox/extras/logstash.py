from contextlib import contextmanager

from docker import DockerClient
from docker.models.containers import Container

from yellowbox.containers import get_ports
from yellowbox.service import SingleContainerService
from yellowbox.utils import _get_spinner

LOGSTASH_DEFAULT_PORT = 5959


class YellowLogstash(SingleContainerService):
    def __init__(self, container: Container, *, _auto_remove=False):
        super().__init__(container)
        self._auto_remove = _auto_remove

    def client_port(self):
        return get_ports(self.container)[LOGSTASH_DEFAULT_PORT]

    @classmethod
    def from_docker(cls, docker_client: DockerClient, image='logstash:latest'):
        container = docker_client.containers.create(
            image, publish_all_ports=True, detach=True)
        return cls(container, _auto_remove=True)

    def stop(self):
        super().stop()
        if self._auto_remove:
            self.container.remove()

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, image='logstash:latest',
            spinner=True) -> 'YellowLogstash':
        spinner = _get_spinner(spinner)
        with spinner("Fetching logstash..."):
            service = cls.from_docker(docker_client, image)

        with service.start():
            yield service
