"""
Azure Blob Storage module, for creating container, uploading files to it and downloading files.
"""
from __future__ import annotations

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError

from yellowbox.containers import create_and_pull, get_ports
from yellowbox.subclasses import SingleContainerService, RunnableWithContext
from yellowbox.utils import LoggingIterableAdapter


BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
DEFAULT_ACCOUNT_NAME = "devstoreaccount1"
STORAGE_URL_FORMAT = "http://127.0.0.1:{port}/{account}"
STORAGE_PASSWORD = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="


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
        self._storage_service = None

    def start(self):
        super().start()
        storage_url = STORAGE_URL_FORMAT.format(port=get_ports(
            self.container)[BLOB_STORAGE_DEFAULT_PORT], account=DEFAULT_ACCOUNT_NAME)
        self._storage_service = BlobServiceClient(
            storage_url, STORAGE_PASSWORD)

    def stop(self, signal: str = 'SIGKILL'):
        super().stop(signal)
        self._storage_service.close()

    def create_container(self, name: str):
        """
        Create blob container.
        Args:
            name - container name.
        """
        with self._storage_service.create_container(name):
            pass

    def upload_files(self, container: str, files: Mapping[str, bytes]):
        """
        Upload files to the given container.
        Creates the container if missing.
        Args:
            container - Container name to upload files to
            files - file_path: data mapping of files to upload.
        """
        try:
            client = self._storage_service.create_container(container)
        except ResourceExistsError:
            client = self._storage_service.get_container_client(container)
        with client:
            for file_path, data in files.items():
                client.upload_blob(file_path, data)

    def download_file(self, container: str, file_path: str) -> bytes:
        """
        Download file from the Azure Blob Storage.
        Args:
            container - container name to download from.
            file_path - File path to download.
        Returns:
            File contents.
        """
        client = self._storage_service.get_container_client(container)
        with client:
            downloader = client.download_blob(file_path)
            return downloader.readall()
