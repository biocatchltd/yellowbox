from yellowbox.containers import create_and_pull
from yellowbox.subclasses import SingleContainerService

BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
DEFAULT_ACCOUNT_NAME = "devstoreaccount1"


class BlobStorageService(SingleContainerService):
    def __init__(self, docker_client,
                 image="mcr.microsoft.com/azure-storage/azurite:latest",
                 *, remove=True):
        container = create_and_pull(docker_client, image)
        super().__init__(container, remove=remove)


