from __future__ import annotations

import tempfile
import typing
from typing import IO

import docker
import pytest
import io

from yellowbox.containers import create_and_pull, download_file, upload_file


def test_upload_file(docker_client):
    container = create_and_pull(docker_client, "alpine:latest",
                                ["cat", "/tmp/test"])
    container.start()
    assert container.wait()["StatusCode"] != 0

    container = docker_client.containers.create("alpine:latest",
                                                ["cat", "/tmp/test"])
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
def test_upload_fileobj(docker_client, fileobj_creation):
    container = create_and_pull(docker_client, "alpine:latest",
                                ["cat", "/tmp/test"])
    with fileobj_creation(b"testfile") as file:
        upload_file(container, "/tmp/test", fileobj=file)
    container.start()
    assert container.wait()["StatusCode"] == 0
    assert download_file(container, "/tmp/test").read() == b"testfile"


def test_download_file(docker_client):
    container = create_and_pull(docker_client, "alpine:latest")
    upload_file(container, "/tmp/test", b"abcd")
    with download_file(container, "/tmp/test") as file:
        assert file.read() == b"abcd"
