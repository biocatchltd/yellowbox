"""
Tests for Azure Storage module
"""
from pytest import mark

from yellowbox.containers import create_and_pull
from yellowbox.extras.azure_storage import BlobStorageService, BLOB_STORAGE_DEFAULT_PORT
from yellowbox.networks import temp_network, connect


@mark.parametrize('spinner', [True, False])
def test_make_azure_storage(docker_client, spinner):
    with BlobStorageService.run(docker_client, spinner=spinner):
        pass


def test_upload_download_files(docker_client):
    with BlobStorageService.run(docker_client) as service:
        service.upload_files("test", {"file_1": b"data", "file_2": b"data2"})
        assert service.download_file("test", "file_1") == b"data"
        assert service.download_file("test", "file_2") == b"data2"


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
