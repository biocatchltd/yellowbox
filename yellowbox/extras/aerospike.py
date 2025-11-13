from contextlib import contextmanager
from typing import Any

import aerospike
from aerospike import exception as aerospike_exception
from docker import DockerClient

from yellowbox import RunMixin
from yellowbox.containers import create_and_pull_with_defaults, get_ports
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, SingleContainerService
from yellowbox.utils import DOCKER_EXPOSE_HOST

__all__ = ["AEROSPIKE_DEFAULT_PORT", "AerospikeService"]

AerospikeError = aerospike_exception.AerospikeError  # aerospike doesn't let you import this on its own

AEROSPIKE_DEFAULT_PORT = 3000


class AerospikeService(SingleContainerService, RunMixin, AsyncRunMixin):
    def __init__(
        self,
        docker_client: DockerClient,
        image="aerospike:ce-6.2.0.3",
        *,
        container_create_kwargs: dict[str, Any] | None = None,
        **kwargs,
    ):
        container = create_and_pull_with_defaults(
            docker_client, image, _kwargs=container_create_kwargs, publish_all_ports=True, detach=True
        )
        self.started = False
        super().__init__(container, **kwargs)

    namespace = "test"

    def client_port(self):
        return get_ports(self.container)[AEROSPIKE_DEFAULT_PORT]

    def _client(self, config: dict[str, Any] | None = None) -> aerospike.Client:
        config = config or {}
        config = {
            **config,
            "hosts": [(DOCKER_EXPOSE_HOST, self.client_port())],
        }
        return aerospike.client(config)

    @contextmanager
    def client(self, config: dict[str, Any] | None = None):
        ret = self._client(config)
        try:
            yield ret
        finally:
            ret.close()

    def start(self, retry_spec: RetrySpec | None = None, **kwargs):
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=15)
        # for some reason it takes time before the container is ready to get a connection
        client = retry_spec.retry(self._client, AerospikeError)
        retry_spec.retry(client.is_connected, AerospikeError)
        self.started = True
        return self

    async def astart(self, retry_spec: RetrySpec | None = None, **kwargs) -> None:
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=15)
        client = await retry_spec.aretry(self._client, AerospikeError)
        await retry_spec.aretry(client.is_connected, AerospikeError)
        self.started = True

    def stop(self, signal="SIGKILL"):
        # change in default
        return super().stop(signal)
