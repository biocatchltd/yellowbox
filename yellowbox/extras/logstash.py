from docker import DockerClient

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.service import ContainerService

LOGSTASH_DEFAULT_PORT = 5959


class LogstashService(ContainerService):
    @property
    def container(self):
        return next(iter(self.containers))

    def client_port(self):
        return get_ports(self.container)[LOGSTASH_DEFAULT_PORT]

    @classmethod
    def _make_containers(cls, docker_client: DockerClient, image='logstash:7.8.1'):
        yield create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True,
            ports={LOGSTASH_DEFAULT_PORT: None}
        )

    def _endpoint_containers(self):
        return self.containers
