from aiohttp import ClientSession, TCPConnector
from gcloud.aio.storage.storage import Storage
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from pytest import MonkeyPatch, fixture, mark, raises
from requests import HTTPError

from tests.util import unique_name_generator
from yellowbox.extras.fake_gcs import FakeGoogleCloudStorage
from yellowbox.networks import connect, temp_network


@mark.parametrize("spinner", [True, False])
def test_make_gcs(docker_client, spinner):
    with FakeGoogleCloudStorage.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_make_gcs_async(docker_client):
    async with FakeGoogleCloudStorage.arun(docker_client):
        pass


@fixture(scope="module")
def http_gcs(docker_client) -> FakeGoogleCloudStorage:
    with FakeGoogleCloudStorage.run(docker_client, scheme="http") as service, MonkeyPatch.context() as monkeypatch:
        # this will only really work for teh standard storage library, for gcloud-aio, we patch with a special
        # function
        monkeypatch.setenv("STORAGE_EMULATOR_HOST", service.local_url())
        yield service


_bucket_name = fixture(unique_name_generator())


@fixture
def _bucket(http_gcs, _bucket_name):
    http_gcs.create_bucket(_bucket_name)
    yield
    http_gcs.delete_bucket(_bucket_name, force=True, missing_ok=True)


@fixture
def bucket_name(_bucket, _bucket_name):
    return _bucket_name


def test_connection_works(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob("a/b/c")
    blob.upload_from_string("mama mia!")

    assert blob.download_as_bytes() == b"mama mia!"


@mark.asyncio
async def test_connection_works_async(http_gcs, bucket_name):
    with http_gcs.patch_gcloud_aio():
        async with ClientSession(connector=TCPConnector(ssl=False)) as session:
            storage = Storage(session=session)
            await storage.upload(bucket_name, "a/b/c", "maya hee")
            data = await storage.download(
                bucket_name,
                "a/b/c",
            )
            assert data == b"maya hee"


def test_connection_works_sibling_network(docker_client, create_and_pull, http_gcs):
    with temp_network(docker_client) as network, connect(network, http_gcs) as aliases:
        url = http_gcs.container_url(aliases[0])
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv -I "{url}"',
            detach=True,
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_connection_works_sibling(docker_client, create_and_pull, http_gcs):
    url = http_gcs.host_url()
    container = create_and_pull(docker_client, "byrnedo/alpine-curl:latest", f'-vvv -I "{url}"', detach=True)
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0


def test_bucket_deletion(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob("a/b/c")
    blob.upload_from_string("mama mia!")
    blob.delete()
    assert not blob.exists()
    http_gcs.delete_bucket(bucket_name)
    assert not bucket.exists()


def test_bucket_bad_deletion(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob("a/b/c")
    blob.upload_from_string("mama mia!")
    with raises(HTTPError):
        http_gcs.delete_bucket(bucket_name)
    assert blob.exists()
    assert bucket.exists()


def test_bucket_force_deletion(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob("a/b/c")
    blob.upload_from_string("mama mia!")
    http_gcs.delete_bucket(bucket_name, force=True)
    assert not blob.exists()
    assert not bucket.exists()


def test_bucket_clear(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    blob = bucket.blob("a/b/c")
    blob.upload_from_string("mama mia!")
    http_gcs.clear_bucket(bucket_name)
    assert not blob.exists()


def test_bucket_clear_with_prefix(http_gcs, bucket_name):
    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
    )

    bucket = client.bucket(bucket_name)
    names = ["my_pretty_goat", "my_pretty_sheep", "my_ugly_dog", "my_poetic_edda", "my_pretty_cow", "my_p"]
    blobs = [bucket.blob(name) for name in names]
    for b in blobs:
        b.upload_from_string(b"abc")
    http_gcs.clear_bucket(bucket_name, prefix="my_p")
    for name, blob in zip(names, blobs):
        assert blob.exists() != name.startswith("my_p"), name
