import json
import os
import sys
from contextlib import contextmanager
from json import JSONDecodeError
from typing import Optional, TextIO

from docker import DockerClient
from docker.errors import BuildError, DockerException, ImageNotFound

from yellowbox.utils import _get_spinner


class DockerfileParseException(BuildError):
    pass


@contextmanager
def build_image(docker_client: DockerClient, image_name: str, remove_image: bool = True,
                file: Optional[TextIO] = sys.stderr, spinner: bool = True, **kwargs):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    Args:
        docker_client: DockerClient to be used to create the image
        image_name: Name of the image to be created
        remove_image: boolean, whether or not to delete the image at the end, default as True
        file: a file-like object (stream); defaults to the current sys.stderr. if set to None, will disable printing
        spinner: boolean, whether or not to use spinner (default as True), note that this param is set to False in
        case `file` param is not None
    """
    if file is None:
        file = open(os.devnull, 'w')
    else:
        spinner = False  # spinner splits into multiple lines in case stream is being printed at the same time
    image_tag = f'{image_name}:test'
    yaspin_spinner = _get_spinner(spinner)
    with yaspin_spinner(f'Creating image {image_tag}...'):
        kwargs = {'tag': image_tag, 'rm': True, 'forcerm': True, **kwargs}
        build_log = docker_client.api.build(**kwargs)
        for msg_b in build_log:
            msgs = str(msg_b, 'utf-8').splitlines()
            for msg in msgs:
                try:
                    parse_msg = json.loads(msg)
                except JSONDecodeError:
                    raise DockerException('error at build logs')
                s = parse_msg.get('stream')
                if s:
                    print(s, end='', flush=True, file=file)
                else:
                    # runtime errors
                    error_detail = parse_msg.get('errorDetail')
                    # parse errors
                    error_msg = parse_msg.get('message')
                    # steps of the image creation
                    status = parse_msg.get('status')
                    # end of process, will contain the ID of the temporary container created at the end
                    aux = parse_msg.get('aux')
                    if error_detail is not None:
                        raise BuildError(reason=error_detail, build_log=None)
                    elif error_msg is not None:
                        raise DockerfileParseException(reason=error_msg, build_log=None)
                    elif status is not None:
                        print(status, end='', flush=True, file=file)
                    elif aux is not None:
                        print(aux, end='', flush=True, file=file)
                    else:
                        raise DockerException(parse_msg)
        yield image_tag
        if remove_image:
            try:
                docker_client.api.remove_image(image_tag)
            except ImageNotFound:
                # if the image was already deleted
                pass
