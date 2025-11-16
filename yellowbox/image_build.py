import json
import sys
from asyncio import get_event_loop
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from io import StringIO
from json import JSONDecodeError
from typing import TextIO
from warnings import warn

from docker import DockerClient
from docker.errors import BuildError, DockerException, ImageNotFound

from yellowbox.utils import _get_spinner


class DockerfileParseError(BuildError):
    pass


DockerfileParseException = DockerfileParseError  # legacy alias


def _docker_build(docker_client: DockerClient, output: TextIO, **kwargs) -> str | None:
    build_log = docker_client.api.build(**kwargs)
    id = None
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
                    if "ID" in aux:
                        # ID, means that the image was created successfully
                        id = aux["ID"]
                else:
                    raise DockerException(parse_msg)
    if id is None:
        raise BuildError("No ID found in build log")
    return id


@contextmanager
def build_image(
    docker_client: DockerClient,
    image_name: str | None,
    remove_image: bool = True,
    file: TextIO | None = ...,  # type: ignore[assignment]
    output: TextIO | None = sys.stderr,
    spinner: bool = True,
    **kwargs,
):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    Args:
        docker_client: DockerClient to be used to create the image
        image_name: Name of the image to be created. If no tag is provided, the tag "test" will be added.
        remove_image: boolean, whether to delete the image at the end, default as True
        file: a file-like object (stream); defaults to the current sys.stderr. if set to None, will disable printing
        spinner: boolean, whether to use spinner (default as True), note that this param is set to False in
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
    kwargs = {"rm": True, "forcerm": True, **kwargs}
    if image_name is None:
        msg = "Creating anonymous image..."
        image_tag = None
    else:
        if ":" in image_name:
            image_tag = image_name
        else:
            image_tag = f"{image_name}:test"
        msg = f"Creating image {image_tag}..."
        kwargs["tag"] = image_tag
    yaspin_spinner = _get_spinner(spinner)
    with yaspin_spinner(msg):
        image_id = _docker_build(docker_client, output, **kwargs)
        image_alias = image_tag if image_tag is not None else image_id
        yield image_alias
        if remove_image:
            try:
                docker_client.api.remove_image(image_alias)
            except ImageNotFound:
                # if the image was already deleted
                pass


@asynccontextmanager
async def async_build_image(
    docker_client: DockerClient,
    image_name: str | None,
    remove_image: bool = True,
    output: TextIO | None = sys.stderr,
    spinner: bool = True,
    **kwargs,
):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    Args:
        docker_client: DockerClient to be used to create the image
        image_name: Name of the image to be created. If no tag is provided, the tag "test" will be added.
        remove_image: boolean, whether to delete the image at the end, default as True
        file: a file-like object (stream)
    """
    # spinner splits into multiple lines in case stream is being printed at the same time
    file = StringIO()
    kwargs = {
        "docker_client": docker_client,
        "output": file,
        "rm": True,
        "forcerm": True,
        **kwargs,
    }
    kwargs = {"rm": True, "forcerm": True, **kwargs}
    if image_name is None:
        start_msg = "Creating anonymous image..."
        fail_msg = "failed building anonymous image"
        ok_msg = "anonymous image built successfully"
        image_tag = None
    else:
        if ":" in image_name:
            image_tag = image_name
        else:
            image_tag = f"{image_name}:test"
        start_msg = f".   Creating image {image_tag}..."
        fail_msg = f"failed building image {image_tag}"
        ok_msg = f".   image {image_tag} built successfully"
        kwargs["tag"] = image_tag
    if spinner and output:
        print(start_msg, file=output)
    try:
        image_id = await get_event_loop().run_in_executor(None, partial(_docker_build, **kwargs))
    except (DockerException, BuildError, DockerfileParseError) as e:
        print(fail_msg, file=sys.stderr)
        print(file.getvalue(), file=sys.stderr)
        raise e

    if spinner and output:
        print(ok_msg, file=output)
        print(file.getvalue(), file=output)

    image_alias = image_id if image_tag is None else image_tag
    yield image_alias
    if remove_image:
        try:
            await get_event_loop().run_in_executor(None, docker_client.api.remove_image, image_alias)
        except ImageNotFound:
            # if the image was already deleted
            pass
