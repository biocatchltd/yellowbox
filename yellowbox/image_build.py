import json
import sys
from asyncio import get_event_loop
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from io import StringIO
from json import JSONDecodeError
from typing import Optional, TextIO
from warnings import warn

from docker import DockerClient
from docker.errors import BuildError, DockerException, ImageNotFound

from yellowbox.utils import _get_spinner


class DockerfileParseError(BuildError):
    pass


DockerfileParseException = DockerfileParseError  # legacy alias


def _docker_build(docker_client: DockerClient, output: TextIO, **kwargs):
    build_log = docker_client.api.build(**kwargs)
    for msg_b in build_log:
        msgs = str(msg_b, "utf-8").splitlines()
        for msg in msgs:
            try:
                parse_msg = json.loads(msg)
            except JSONDecodeError as e:
                raise DockerException("error at build logs") from e
            s = parse_msg.get("stream")
            if s and output:
                print(s, end="", flush=True, file=output)
            else:
                # runtime errors
                error_detail = parse_msg.get("errorDetail")
                # parse errors
                error_msg = parse_msg.get("message")
                # steps of the image creation
                status = parse_msg.get("status")
                # end of process, will contain the ID of the temporary container created at the end
                aux = parse_msg.get("aux")
                if error_detail is not None:
                    raise BuildError(reason=error_detail, build_log=None)
                elif error_msg is not None:
                    raise DockerfileParseError(reason=error_msg, build_log=None)
                elif status is not None and output:
                    print(status, end="", flush=True, file=output)
                elif aux is not None and output:
                    print(aux, end="", flush=True, file=output)
                else:
                    raise DockerException(parse_msg)


@contextmanager
def build_image(
    docker_client: DockerClient,
    image_name: str,
    remove_image: bool = True,
    file: Optional[TextIO] = ...,  # type: ignore[assignment]
    output: Optional[TextIO] = sys.stderr,
    spinner: bool = True,
    **kwargs,
):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    Args:
        docker_client: DockerClient to be used to create the image
        image_name: Name of the image to be created. If no tag is provided, the tag "test" will be added.
        remove_image: boolean, whether or not to delete the image at the end, default as True
        file: a file-like object (stream); defaults to the current sys.stderr. if set to None, will disable printing
        spinner: boolean, whether or not to use spinner (default as True), note that this param is set to False in
        case `file` param is not None
    """
    spinner = spinner and file is None
    if file is not ...:
        warn(
            "The `file` parameter is deprecated and will be removed in a future version",
            DeprecationWarning,
            stacklevel=1,
        )
        output = file

    # spinner splits into multiple lines in case stream is being printed at the same time
    if ":" in image_name:
        image_tag = image_name
    else:
        image_tag = f"{image_name}:test"
    yaspin_spinner = _get_spinner(spinner)
    with yaspin_spinner(f"Creating image {image_tag}..."):
        kwargs = {"tag": image_tag, "rm": True, "forcerm": True, **kwargs}
        _docker_build(docker_client, output, **kwargs)
        yield image_tag
        if remove_image:
            try:
                docker_client.api.remove_image(image_tag)
            except ImageNotFound:
                # if the image was already deleted
                pass


@asynccontextmanager
async def async_build_image(
    docker_client: DockerClient,
    image_name: str,
    remove_image: bool = True,
    output: Optional[TextIO] = sys.stderr,
    spinner: bool = True,
    **kwargs,
):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    Args:
        docker_client: DockerClient to be used to create the image
        image_name: Name of the image to be created. If no tag is provided, the tag "test" will be added.
        remove_image: boolean, whether or not to delete the image at the end, default as True
        file: a file-like object (stream)
    """
    # spinner splits into multiple lines in case stream is being printed at the same time
    if ":" in image_name:
        image_tag = image_name
    else:
        image_tag = f"{image_name}:test"
    file = StringIO()
    kwargs = {
        "docker_client": docker_client,
        "output": file,
        "tag": image_tag,
        "rm": True,
        "forcerm": True,
        **kwargs,
    }
    if spinner and output:
        print(f".   building image {image_tag}...", file=output)
    try:
        await get_event_loop().run_in_executor(None, partial(_docker_build, **kwargs))
    except (DockerException, BuildError, DockerfileParseError) as e:
        print(f"failed building image {image_tag}", file=sys.stderr)
        print(file.getvalue(), file=sys.stderr)
        raise e
    else:
        if spinner and output:
            print(f".   image {image_tag} built successfully", file=output)
            print(file.getvalue(), file=output)

    yield image_tag
    if remove_image:
        try:
            await get_event_loop().run_in_executor(None, docker_client.api.remove_image, image_tag)
        except ImageNotFound:
            # if the image was already deleted
            pass
