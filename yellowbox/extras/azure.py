from yellowbox.containers import create_and_pull

BLOB_STORAGE_DEFAULT_PORT = 10000
DEFAULT_ACCOUNT_KEY =

class BlobStorageService(...):
    def __init__(self, docker_client,
                 image="mcr.microsoft.com/azure-storage/azurite:latest"):
        container = create_and_pull(docker_client, image)
        super().__init__(container)


