from asyncio import gather
from time import sleep

from docker.errors import BuildError, DockerException, ImageNotFound
from pytest import mark, raises

from yellowbox import async_build_image, build_image


@mark.xfail(reason="I really don't know why it succeeds locally for me but fails on Github.")
@mark.parametrize("image_name", ["yellowbox", "yellowbox:test", None])
def test_valid_image_build(docker_client, image_name):
    with build_image(
        docker_client, image_name, path=".", dockerfile="tests/resources/valid_dockerfile/Dockerfile"
    ) as image:
        # sometimes we need to wait for the image to be acknowledged by docker
        sleep(1)
        container = docker_client.containers.create(image)
        container.start()
        container.wait()  # wait for the container to end and close
        container.remove()
    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create(image)


@mark.asyncio
@mark.parametrize("image1_name", ["yellowbox:test1", None])
@mark.parametrize("image2_name", ["yellowbox:test2", None])
async def test_valid_image_build_async(docker_client, image1_name, image2_name):
    building_tasks = [
        async_build_image(
            docker_client,
            image_name=image1_name,
            path=".",
            dockerfile="tests/resources/valid_dockerfile/Dockerfile",
        ),
        async_build_image(
            docker_client,
            image_name=image2_name,
            path=".",
            dockerfile="tests/resources/valid_dockerfile/Dockerfile",
        ),
    ]
    image0, image1 = await gather(*(s.__aenter__() for s in building_tasks))
    # sometimes we need to wait for the image to be acknowledged by docker
    sleep(1)
    first_container = docker_client.containers.create(image0)
    first_container.start()
    first_container.wait()  # wait for the container to end and close
    first_container.remove()

    second_container = docker_client.containers.create(image1)
    second_container.start()
    second_container.wait()  # wait for the container to end and close
    second_container.remove()
    await gather(*(s.__aexit__(None, None, None) for s in building_tasks))

    # out of contextmanager, image should be deleted
    with raises(ImageNotFound):
        docker_client.containers.create(image0)
    with raises(ImageNotFound):
        docker_client.containers.create(image1)


@mark.asyncio
@mark.parametrize("image_name", ["yellowbox", "yellowbox:test", None])
async def test_invalid_image_build_async(docker_client, capsys, image_name):
    async def build():
        async with async_build_image(
            docker_client,
            image_name=image_name,
            path=".",
            dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile",
        ) as image:
            docker_client.containers.create(image)

    with raises(BuildError):
        await build()

    captured = capsys.readouterr()
    assert "Step 1/3 : FROM alpine:3" in captured.err
    assert "Step 2/3 : RUN apk update" in captured.err
    assert "Step 3/3 : RUN file_not_exists.sh" in captured.err
    assert "file_not_exists.sh: not found" in captured.err


@mark.parametrize("image_name", ["yellowbox", "yellowbox:test", None])
def test_invalid_parse_image_build(docker_client, image_name):
    with raises(DockerException), build_image(
        docker_client, image_name, path=".", dockerfile="tests/resources/invalid_parse_dockerfile/Dockerfile"
    ):
        pass


@mark.parametrize("image_name", ["yellowbox", "yellowbox:test", None])
def test_invalid_run_image_build(docker_client, image_name):
    with raises(DockerException), build_image(
        docker_client, image_name, path=".", dockerfile="tests/resources/invalid_run_dockerfile/Dockerfile"
    ):
        pass
