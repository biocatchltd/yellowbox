from asyncio import gather

from docker.errors import BuildError, DockerException, ImageNotFound
from pytest import mark, raises

from yellowbox import async_build_image, build_image


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
    building_tasks = [
        async_build_image(
            docker_client,
            image_name="yellowbox:test1",
            path=".",
            dockerfile="tests/resources/valid_dockerfile/Dockerfile",
        ),
        async_build_image(
            docker_client,
            image_name="yellowbox:test2",
            path=".",
            dockerfile="tests/resources/valid_dockerfile/Dockerfile",
        ),
    ]
    images = await gather(*(s.__aenter__() for s in building_tasks))
    first_container = docker_client.containers.create(images[0])
    first_container.start()
    first_container.wait()  # wait for the container to end and close
    first_container.remove()

    second_container = docker_client.containers.create(images[1])
    second_container.start()
    second_container.wait()  # wait for the container to end and close
    second_container.remove()
    await gather(*(s.__aexit__(None, None, None) for s in building_tasks))

    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create("yellowbox:test1")
    with raises(ImageNotFound):
        docker_client.containers.create("yellowbox:test2")


@mark.asyncio
async def test_invalid_image_build_async(docker_client):
    with raises(BuildError), build_image(
        docker_client,
        image_name="yellowbox:test2",
        path=".",
        dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile",
    ) as image:
        docker_client.containers.create(image)


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
