from azure.storage.blob import BlobServiceClient
from pytest import fixture, mark

from tests.util import unique_name_generator
from yellowbox.extras.azure_storage import (
    BLOB_STORAGE_DEFAULT_PORT,
    DEFAULT_ACCOUNT_KEY,
    DEFAULT_ACCOUNT_NAME,
    AzuriteService,
)
from yellowbox.networks import connect, temp_network
from yellowbox.utils import DOCKER_EXPOSE_HOST, docker_host_name


@mark.parametrize("spinner", [True, False])
def test_make_azure_storage(docker_client, spinner):
    with AzuriteService.run(docker_client, spinner=spinner):
        pass

def test_sanity(docker_client):
    with AzuriteService.run(docker_client) as service:
        port = service.client_port()
        with BlobServiceClient(
            f"http://{DOCKER_EXPOSE_HOST}:{port}/{DEFAULT_ACCOUNT_NAME}", DEFAULT_ACCOUNT_KEY
        ) as client, client.create_container("test") as container:
            container.upload_blob("file_1", b"data")
            downloader = container.download_blob("file_1")
            assert downloader.readall() == b"data"


@mark.asyncio
async def test_sanity_async(docker_client):
    async with AzuriteService.arun(docker_client) as service:
        port = service.client_port()
        with BlobServiceClient(
            f"http://{DOCKER_EXPOSE_HOST}:{port}/{DEFAULT_ACCOUNT_NAME}", DEFAULT_ACCOUNT_KEY
        ) as client, client.create_container("test") as container:
            container.upload_blob("file_1", b"data")
            downloader = container.download_blob("file_1")
            assert downloader.readall() == b"data"


@fixture(scope="module")
def azurite_service(docker_client):
    with AzuriteService.run(docker_client, spinner=False) as blob:
        yield blob


container_name = fixture(unique_name_generator())


def test_connection_works_sibling_network(docker_client, create_and_pull, azurite_service):
    with temp_network(docker_client) as network, connect(network, azurite_service) as aliases:
        url = f"http://{aliases[0]}:{BLOB_STORAGE_DEFAULT_PORT}"
        container = create_and_pull(
            docker_client, "byrnedo/alpine-curl:latest", f'-vvv -I "{url}" --http0.9', detach=True
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_connection_works_sibling(docker_client, create_and_pull, azurite_service):
    port = azurite_service.client_port()
    url = f"http://{docker_host_name}:{port}"
    container = create_and_pull(docker_client, "byrnedo/alpine-curl:latest", f'-vvv -I "{url}" --http0.9', detach=True)
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0


def test_connection_string(azurite_service):
    BlobServiceClient.from_connection_string(azurite_service.connection_string)


def test_container_connection_string(docker_client, create_and_pull, azurite_service, container_name):
    with temp_network(docker_client) as network:
        client = BlobServiceClient.from_connection_string(azurite_service.connection_string)
        client.create_container(container_name)
        azurite_service.connect(network)
        container = create_and_pull(
            docker_client,
            "mcr.microsoft.com/azure-cli:latest",
            [
                "az",
                "storage",
                "blob",
                "list",
                "--connection-string",
                azurite_service.container_connection_string,
                "--container-name",
                container_name,
            ],
            detach=True,
            network=network.name,
        )
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0


def test_host_connection_string(docker_client, create_and_pull, azurite_service, container_name):
    client = BlobServiceClient.from_connection_string(azurite_service.connection_string)
    client.create_container(container_name)
    container = create_and_pull(
        docker_client,
        "mcr.microsoft.com/azure-cli:latest",
        [
            "az",
            "storage",
            "blob",
            "list",
            "--connection-string",
            azurite_service.host_connection_string,
            "--container-name",
            container_name,
        ],
        detach=True,
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0
