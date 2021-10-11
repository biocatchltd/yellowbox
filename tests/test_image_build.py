from time import sleep

from docker.errors import ImageNotFound
from pytest import raises

from yellowbox import image_build
from yellowbox.image_build import DockerBuildFailure, DockerfileParseException


def test_valid_image_build(docker_client):
    with image_build(docker_client, "yellowbox", path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"):
        container = docker_client.containers.create('yellowbox:test', ports={80: 80})
        container.start()
        sleep(3)  # wait for the container to end and close
        container.remove()
    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create('yellowbox:test', ports={80: 80})


def test_invalid_parse_image_build(docker_client):
    with raises(DockerfileParseException):
        with image_build(docker_client, "yellowbox", path=".",
                         dockerfile="tests/resources/invalid_parse_dockerfile/Dockerfile") as error:
            assert "ARG requires at least one argument" in error


def test_invalid_run_image_build(docker_client):
    with raises(DockerBuildFailure):
        with image_build(docker_client, "yellowbox", path=".",
                         dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile") as error:
            assert error['code'] == 127
