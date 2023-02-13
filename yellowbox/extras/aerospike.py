from typing import Any, Dict, Optional

from docker import DockerClient
import aerospike

from yellowbox import RunMixin
from yellowbox.containers import create_and_pull, get_ports
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, SingleContainerService
from yellowbox.utils import DOCKER_EXPOSE_HOST

__all__ = ['AerospikeService', 'AEROSPIKE_DEFAULT_PORT']

AerospikeError = aerospike.exception.AerospikeError  # aerospike doesn't let you import this on its own


AEROSPIKE_DEFAULT_PORT = 3000


class AerospikeService(SingleContainerService, RunMixin, AsyncRunMixin):
    def __init__(self, docker_client: DockerClient, image='aerospike/aerospike-server-enterprise:latest', **kwargs):
        container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True)
        self.started = False
        self.config = {
            'policies': {
                'write': {
                    'durable_delete': True
                },
                'apply': {
                    'durable_delete': True
                }
            }
        }
        self.client = None
        super().__init__(container, **kwargs)

    def client_port(self):
        return get_ports(self.container)[AEROSPIKE_DEFAULT_PORT]

    def add_to_config(self, config: Dict[str, Any]):
        self.config.update(config)

    def start(self, retry_spec: Optional[RetrySpec] = None, **kwargs):
        super().start()
        self.add_to_config({'hosts': [(DOCKER_EXPOSE_HOST, self.client_port())], **kwargs})
        retry_spec = retry_spec or RetrySpec(attempts=15)

        def create_client():
            # it works even without the connect() method, not sure why it is needed
            return aerospike.client(self.config).connect()

        # for some reason it takes time before the container is ready to get a connection
        self.client = retry_spec.retry(create_client, AerospikeError)
        retry_spec.retry(self.client.is_connected, AerospikeError)
        self.started = True
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None, **kwargs) -> None:
        super().start()
        self.add_to_config({'hosts': [(DOCKER_EXPOSE_HOST, self.client_port())], **kwargs})
        retry_spec = retry_spec or RetrySpec(attempts=15)
        await retry_spec.aretry(self.client, AerospikeError)
        await retry_spec.aretry(self.client().is_connected, AerospikeError)
        self.started = True

    def stop(self, signal='SIGKILL'):
        # change in default
        return super().stop(signal)

    @property
    def namespace(self) -> str:
        # the aerospike image comes with 'test' namespace as default
        return "test"
