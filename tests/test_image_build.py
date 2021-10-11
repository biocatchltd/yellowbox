from docker.errors import ImageNotFound
from pytest import raises

from yellowbox import build_image
from yellowbox.image_build import DockerBuildFailure, DockerfileParseException


def test_valid_image_build(docker_client):
    with build_image(docker_client, "yellowbox", path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"):
        container = docker_client.containers.create('yellowbox:test')
        container.start()
        container.wait()  # wait for the container to end and close
        container.remove()
    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create('yellowbox:test')


def test_invalid_parse_image_build(docker_client):
    with raises(DockerfileParseException) as execinfo:
        with build_image(docker_client, "yellowbox", path=".",
                         dockerfile="tests/resources/invalid_parse_dockerfile/Dockerfile"):
            pass
    assert "ARG requires at least one argument" in execinfo.value.message


def test_invalid_run_image_build(docker_client):
    with raises(DockerBuildFailure) as execinfo:
        with build_image(docker_client, "yellowbox", path=".",
                         dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile"):
            pass
    assert execinfo.value.message['code'] == 127
