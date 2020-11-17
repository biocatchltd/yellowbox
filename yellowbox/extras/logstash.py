from typing import Optional

from docker import DockerClient

from yellowbox.retry import RetrySpec
from yellowbox.containers import get_ports, create_and_pull
from yellowbox.subclasses import SingleContainerService, RunMixin

__all__ = ['LogstashService', 'LOGSTASH_DEFAULT_PORT']

LOGSTASH_DEFAULT_PORT = 5959


class LogstashService(SingleContainerService, RunMixin):
    def __init__(self, docker_client: DockerClient, image='logstash:7.8.1', **kwargs):
        super().__init__(create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True,
            ports={LOGSTASH_DEFAULT_PORT: None}
        ), **kwargs)

    def start(self, retry_spec: Optional[RetrySpec] = None):
        # for now we just start the service, re-implementing this service is an ongoing ticket
        return super().start(retry_spec)

    def client_port(self):
        return get_ports(self.container)[LOGSTASH_DEFAULT_PORT]

    def stop(self, signal='SIGKILL'):
        # change in default
        return super().stop(signal)
