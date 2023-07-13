from pytest import mark
from docker.errors import DockerException, ImageNotFound
from pytest import raises

from yellowbox import build_image, build_docker_image
from pytest import fixture
import asyncio


# @fixture(scope='session')
# def event_loop(request):
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


def test_valid_image_build(docker_client):
    with build_image(
        docker_client, "yellowbox", path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"
    ) as image:
        container = docker_client.containers.create(image)
        container.start()
        container.wait()  # wait for the container to end and close
        container.remove()
    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create("yellowbox:test")


@mark.asyncio
async def test_valid_image_build_async(docker_client):
    # with build_docker_image(
    build_docker_image(
    docker_client, "yellowbox", path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"
    )
        # print(image)
    # async with async_build_image(
    #     docker_client, "yellowbox", path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"
    # ) as image:
    #     container = docker_client.containers.create(image)
    #     container.start()
    #     container.wait()  # wait for the container to end and close
    #     container.remove()
    # # out of contextmanager, image should be deleted
    # with raises(ImageNotFound):
    #     docker_client.containers.create("yellowbox:test")


def test_invalid_parse_image_build(docker_client):
    with raises(DockerException), build_image(
        docker_client, "yellowbox", path=".", dockerfile="tests/resources/invalid_parse_dockerfile/Dockerfile"
    ):
        pass


def test_invalid_run_image_build(docker_client):
    with raises(DockerException), build_image(
        docker_client, "yellowbox", path=".", dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile"
    ):
        pass
