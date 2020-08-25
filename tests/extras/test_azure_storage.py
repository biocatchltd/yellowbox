from pytest import mark

from yellowbox.containers import get_ports, create_and_pull
from yellowbox.extras.azure_storage import BlobStorageService, BLOB_STORAGE_DEFAULT_PORT


@mark.parametrize('spinner', [True, False])
def test_make_azure_storage(docker_client, spinner):
    with BlobStorageService.run(docker_client, spinner=spinner):
        pass

def test_upload_download_files(docker_client):
    with BlobStorageService.run(docker_client) as service:
        service.upload_files("test", {"file_1": b"data", "file_2": b"data2"})
        assert service.download_file("test", "file_1") == b"data"
        assert service.download_file("test", "file_2") == b"data2"
