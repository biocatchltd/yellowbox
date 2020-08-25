from docker import DockerClient

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.subclasses import SingleContainerService, RunMixin

LOGSTASH_DEFAULT_PORT = 5959


class LogstashService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='logstash:7.8.1', **kwargs):
        super().__init__(create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True,
            ports={LOGSTASH_DEFAULT_PORT: None}
        ), **kwargs)

    def client_port(self):
        return get_ports(self.container)[LOGSTASH_DEFAULT_PORT]
