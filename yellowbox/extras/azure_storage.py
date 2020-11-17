"""
Azure Blob Storage module, for creating container, uploading files to it and downloading files.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Union

from docker import DockerClient
from docker.models.networks import Network

from yellowbox.containers import create_and_pull, get_ports, short_id
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import SingleContainerService, RunMixin

__all__ = ['BlobStorageService']

BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
DEFAULT_ACCOUNT_NAME = "devstoreaccount1"
STORAGE_URL_FORMAT = "http://127.0.0.1:{port}/{account}"


class _ResourceNotReady(Exception):
    pass


class BlobStorageService(SingleContainerService, RunMixin):
    """
    Starts Azurite, Azure's storage emulator.
    Provides helper functions for preparing the instance for testing.
    TODO: Make account name and key configurable.
    """
    account_name = DEFAULT_ACCOUNT_NAME
    account_key = DEFAULT_ACCOUNT_KEY

    def __init__(self, docker_client: DockerClient,
                 image: str = "mcr.microsoft.com/azure-storage/azurite:latest",
                 **kwargs):
        container = create_and_pull(
            docker_client, image, "azurite-blob --blobHost 0.0.0.0", publish_all_ports=True)
        super().__init__(container, **kwargs)

    def stop(self, signal: Union[str, int] = 'SIGKILL'):
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
            f"BlobEndpoint=http://localhost:{self.client_port()}/{self.account_name};")

    @property
    def container_connection_string(self):
        """Connection string to connect across containers in the same network"""
        return (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"BlobEndpoint="
            f"http://{short_id(self.container)}:{BLOB_STORAGE_DEFAULT_PORT}/{self.account_name};")

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()

        def check_ready():
            if b"Azurite Blob service successfully listens on" not in self.container.logs():
                raise _ResourceNotReady

        retry_spec = retry_spec or RetrySpec(attempts=10)

        retry_spec.retry(check_ready, _ResourceNotReady)
        return self

    def connect(self, network: Network, aliases: Optional[List[str]] = None,
                **kwargs) -> Sequence[str]:
        # Make sure the id is in the aliases list. Needed for the container
        # connection string.
        if aliases is not None:
            aliases.append(short_id(self.container))
        return super().connect(network, aliases=aliases, **kwargs)
