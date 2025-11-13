from __future__ import annotations

import io
import tempfile
from time import sleep
from typing import IO

import pytest
from pytest import mark

from yellowbox.containers import download_file, is_removed, removing, upload_file
from yellowbox.image_build import build_image


def test_upload_file(docker_client, create_and_pull):
    container = create_and_pull(docker_client, "alpine:latest", ["cat", "/tmp/test"], remove=True)
    container.start()
    assert container.wait()["StatusCode"] != 0

    container = create_and_pull(docker_client, "alpine:latest", ["cat", "/tmp/test"])
    upload_file(container, "/tmp/test", b"testfile")
    container.start()
    assert container.wait()["StatusCode"] == 0
    assert download_file(container, "/tmp/test").read() == b"testfile"


def _create_temp_file(data: bytes) -> IO[bytes]:
    f = tempfile.TemporaryFile()
    f.write(data)
    f.seek(0)
    return f


@pytest.mark.parametrize("fileobj_creation", [io.BytesIO, _create_temp_file])
def test_upload_fileobj(docker_client, fileobj_creation, create_and_pull):
    container = create_and_pull(docker_client, "alpine:latest", ["cat", "/tmp/test"])
    with fileobj_creation(b"testfile") as file:
        upload_file(container, "/tmp/test", fileobj=file)
    container.start()
    assert container.wait()["StatusCode"] == 0
    assert download_file(container, "/tmp/test").read() == b"testfile"


def test_download_file(docker_client, create_and_pull):
    container = create_and_pull(docker_client, "alpine:latest")
    upload_file(container, "/tmp/test", b"abcd")
    with download_file(container, "/tmp/test") as file:
        assert file.read() == b"abcd"


@pytest.mark.parametrize("expected_exit_code", [0, None, (1, 0)])
def test_removing(docker_client, create_and_pull, expected_exit_code):
    container = create_and_pull(docker_client, "alpine:latest", "sh -c exit 0")
    with removing(container, expected_exit_code=expected_exit_code):
        container.start()
        assert container.wait()["StatusCode"] == 0
    assert is_removed(container)


@pytest.mark.parametrize("expected_exit_code", [1, (1, 12)])
def test_removing_fails(docker_client, create_and_pull, expected_exit_code):
    container = create_and_pull(docker_client, "alpine:latest", "sh -c exit 0")
    with pytest.raises(RuntimeError), removing(container, expected_exit_code=expected_exit_code):
        container.start()
    assert container.wait()["StatusCode"] == 0
    assert not is_removed(container)


def test_create_and_pull(docker_client, create_and_pull):
    container = create_and_pull(docker_client, "alpine:latest", "sh -c exit 0")
    assert "alpine:latest" in container.image.tags


def test_create_and_pull_notag(docker_client, create_and_pull):
    # we create an anonymous image to test this
    with build_image(docker_client, None, path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile") as image:
        # sometimes we need to wait for the image to be acknowledged by docker
        sleep(1)
        container = create_and_pull(docker_client, image, "sh -c exit 0")
        assert container.image.tags == []
        with removing(container):
            container.start()
            assert container.wait()["StatusCode"] == 0


@mark.xfail(reason="I really don't know why it fails on Github but succeeds locally.")
@mark.parametrize("image_name", ["yellowbox", "yellowbox:test", None])
def test_build_create_and_pull(docker_client, create_and_pull, image_name):
    # we create an anonymous image to test this
    with build_image(
        docker_client, image_name, path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"
    ) as image:
        # sometimes we need to wait for the image to be acknowledged by docker
        sleep(1)
        container = create_and_pull(docker_client, image, "sh -c exit 0")
        expected_tags = [] if image_name is None else ["yellowbox:test"]
        assert container.image.tags == expected_tags
        with removing(container):
            container.start()
            assert container.wait()["StatusCode"] == 0
