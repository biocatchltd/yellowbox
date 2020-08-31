"""
Azure Blob Storage module, for creating container, uploading files to it and downloading files.
"""
from __future__ import annotations

from typing import Union

from docker import DockerClient

from yellowbox.containers import create_and_pull, get_ports
from yellowbox.subclasses import SingleContainerService, RunMixin
from yellowbox.utils import retry
import textwrap

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

    def __init__(self, docker_client: DockerClient, image: str = "mcr.microsoft.com/azure-storage/azurite:latest",
                 **kwargs):
        container = create_and_pull(
            docker_client, image, "azurite-blob --blobHost 0.0.0.0", publish_all_ports=True)
        super().__init__(container, **kwargs)
        self.account_name = DEFAULT_ACCOUNT_NAME
        self.account_key = DEFAULT_ACCOUNT_KEY

    def stop(self, signal: Union[str, int] = 'SIGKILL'):
        """
        We override to change the signal.
        """
        super().stop(signal)

    def client_port(self):
        return get_ports(self.container)[BLOB_STORAGE_DEFAULT_PORT]

    @property
    def connection_string(self):
        return textwrap.dedent(f"""
        DefaultEndpointsProtocol = http;
        AccountName = {self.account_name};
        AccountKey = {self.account_key};
        BlobEndpoint = http://localhost:{self.client_port()}/{self.account_name};
        """).replace("\n", "")

    def start(self):
        super().start()

        def check_ready():
            if b"Azurite Blob service successfully listens on" not in self.container.logs():
                raise _ResourceNotReady

        retry(check_ready, _ResourceNotReady)
        return self
