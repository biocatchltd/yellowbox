"""
Azure Blob Storage module, for creating container, uploading files to it and downloading files.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from docker import DockerClient
from docker.models.networks import Network

from yellowbox.containers import create_and_pull_with_defaults, get_ports, short_id
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, RunMixin, SingleContainerService

__all__ = ["AzuriteService", "BlobStorageService"]

from yellowbox.utils import DOCKER_EXPOSE_HOST, docker_host_name

BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
DEFAULT_ACCOUNT_NAME = "devstoreaccount1"


class _ResourceNotReadyError(Exception):
    pass


class AzuriteService(SingleContainerService, RunMixin, AsyncRunMixin):
    """
    Starts Azurite, Azure's storage emulator.
    Provides helper functions for preparing the instance for testing.
    TODO: Make account name and key configurable.
    """

    account_name = DEFAULT_ACCOUNT_NAME
    account_key = DEFAULT_ACCOUNT_KEY

    def __init__(
        self,
        docker_client: DockerClient,
        image: str = "mcr.microsoft.com/azure-storage/azurite:latest",
        *,
        container_create_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        container = create_and_pull_with_defaults(
            docker_client,
            image,
            "azurite-blob --blobHost 0.0.0.0",
            _kwargs=container_create_kwargs,
            publish_all_ports=True,
        )
        super().__init__(container, **kwargs)

    def stop(self, signal: Union[str, int] = "SIGKILL"):
        """
        We override to change the signal.
        """
        super().stop(signal)

    def client_port(self):
        return get_ports(self.container)[BLOB_STORAGE_DEFAULT_PORT]

    @property
    def connection_string(self):
        """Connection string to connect from host to container"""
        return (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"BlobEndpoint={self.endpoint_url};"
        )

    @property
    def container_connection_string(self):
        """Connection string to connect across containers in the same network"""
        return (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"BlobEndpoint={self.container_endpoint_url};"
        )

    @property
    def host_connection_string(self):
        """Connection string to connect across containers through the docker host"""
        return (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"BlobEndpoint={self.host_endpoint_url};"
        )

    @property
    def endpoint_url(self):
        """URL for the endpoint from docker host"""
        return f"http://{DOCKER_EXPOSE_HOST}:{self.client_port()}/{self.account_name}"

    @property
    def container_endpoint_url(self):
        """URL for the endpoint from another container over a common network"""
        return f"http://{short_id(self.container)}:{BLOB_STORAGE_DEFAULT_PORT}/{self.account_name}"

    @property
    def host_endpoint_url(self):
        """URL for the endpoint from another container through the docker host"""
        return f"http://{docker_host_name}:{self.client_port()}/{self.account_name}"

    @property
    def account_credentials(self):
        """Azure credentials dict to connect to the service"""
        return {"account_name": self.account_name, "account_key": self.account_key}

    def _check_ready(self):
        if b"Azurite Blob service successfully listens on" not in self.container.logs():
            raise _ResourceNotReadyError

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()

        retry_spec = retry_spec or RetrySpec(attempts=10)

        retry_spec.retry(self._check_ready, _ResourceNotReadyError)
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None):
        super().start()

        retry_spec = retry_spec or RetrySpec(attempts=10)

        await retry_spec.aretry(self._check_ready, _ResourceNotReadyError)
        return self

    def connect(self, network: Network, aliases: Optional[List[str]] = None, **kwargs) -> Sequence[str]:
        # Make sure the id is in the aliases list. Needed for the container
        # connection string.
        if aliases is not None:
            aliases.append(short_id(self.container))
        return super().connect(network, aliases=aliases, **kwargs)


# legacy alias
BlobStorageService = AzuriteService
