from docker.errors import DockerException, ImageNotFound
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
    async with async_build_image(
        docker_client,
        image_name="yellowbox:test1",
        path=".",
        dockerfile="tests/resources/valid_dockerfile/Dockerfile",
        remove_image=True,
    ) as first_image:
        async with async_build_image(
            docker_client,
            image_name="yellowbox:test2",
            path=".",
            dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile",
            remove_image=True,
        ) as second_image:
            first_container = docker_client.containers.create(first_image)
            first_container.start()
            first_container.wait()  # wait for the container to end and close

            # The second_image must not exist because not created
            with raises(ImageNotFound):
                docker_client.containers.create(second_image)

    # The first_image must not exist because deleted
    with raises(ImageNotFound):
        docker_client.containers.create(first_image)


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
