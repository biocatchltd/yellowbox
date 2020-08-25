"""
Azure Blob Storage module, for creating container, uploading files to it and downloading files.
"""
from __future__ import annotations

from yellowbox.containers import create_and_pull, get_ports
from yellowbox.subclasses import SingleContainerService, RunnableWithContext


BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
DEFAULT_ACCOUNT_NAME = "devstoreaccount1"
STORAGE_URL_FORMAT = "http://127.0.0.1:{port}/{account}"


class BlobStorageService(SingleContainerService, RunnableWithContext):
    """
    Starts Azurite, Azure's storage emulator.
    Provides helper functions for preparing the instance for testing.
    TODO: Make account name and key configurable.
    """

    def __init__(self, docker_client,
                 image="mcr.microsoft.com/azure-storage/azurite:latest",
                 *, remove=True):
        container = create_and_pull(
            docker_client, image, "azurite-blob --blobHost 0.0.0.0", publish_all_ports=True)
        super().__init__(container, remove=remove)


    def stop(self, signal: str = 'SIGKILL'):
        """
        We override to change the signal.
        """
        super().stop(signal)

    def client_port(self):
        return get_ports(self.container)[BLOB_STORAGE_DEFAULT_PORT]