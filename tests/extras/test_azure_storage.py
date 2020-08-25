"""
Tests for Azure Storage module
"""
from pytest import mark

from azure.storage.blob import BlobServiceClient
from yellowbox.containers import create_and_pull, get_ports
from yellowbox.extras.azure_storage import BlobStorageService, BLOB_STORAGE_DEFAULT_PORT, DEFAULT_ACCOUNT_KEY, \
                                            DEFAULT_ACCOUNT_NAME
from yellowbox.networks import temp_network, connect


@mark.parametrize('spinner', [True, False])
def test_make_azure_storage(docker_client, spinner):
    with BlobStorageService.run(docker_client, spinner=spinner):
        pass

def test_sanity(docker_client):
    with BlobStorageService.run(docker_client) as service:
        port = service.client_port()
        with BlobServiceClient(f"http://127.0.0.1:{port}/{DEFAULT_ACCOUNT_NAME}", DEFAULT_ACCOUNT_KEY) as client:
            with client.create_container("test") as container:
                container.upload_blob("file_1", b"data")
                downloader = container.download_blob("file_1")
                assert downloader.readall() == b"data"


def test_connection_works_sibling_network(docker_client):
    with temp_network(docker_client) as network:
        with BlobStorageService.run(docker_client) as blob, \
                connect(network, blob) as aliases:
            url = f"http://{aliases[0]}:{BLOB_STORAGE_DEFAULT_PORT}"
            container = create_and_pull(
                docker_client,
                "byrnedo/alpine-curl", f'-vvv -I "{url}" --http0.9',
                detach=True
            )
            with connect(network, container):
                container.start()
                return_status = container.wait()
                assert return_status["StatusCode"] == 0
