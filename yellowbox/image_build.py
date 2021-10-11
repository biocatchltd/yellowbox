import json
import sys
from contextlib import contextmanager
from typing import Any, Dict, Union

from docker import DockerClient


class DockerBuildException(Exception):
    def __init__(self, message: Union[str, Dict[str, Any]]) -> None:
        self.message = message


class DockerfileParseException(DockerBuildException):
    pass


class DockerBuildFailure(DockerBuildException):
    pass


@contextmanager
def image_build(docker_client: DockerClient, image_name: str, remove_image: bool = True, *args, **kwargs):
    """
    Create a docker image (similar to docker build command)
    At the end, deletes the image (using rmi command)
    """
    image_tag = f'{image_name}:test'
    build_log = docker_client.api.build(tag=image_tag, rm=True, forcerm=True, *args, **kwargs)
    for msg_b in build_log:
        msgs = str(msg_b, 'utf-8').splitlines()
        for msg in msgs:
            parse_msg = json.loads(msg)
            s = parse_msg.get('stream')
            if s:
                print(s, end='', flush=True, file=sys.stderr)
            else:
                error_detail = parse_msg.get('errorDetail')
                error_msg = parse_msg.get('message')  # for parse errors
                status = parse_msg.get('status')
                aux = parse_msg.get('aux')
                if error_detail:
                    raise DockerBuildFailure(error_detail)
                elif error_msg:
                    raise DockerfileParseException(error_msg)
                elif status:
                    print(status, end='', flush=True, file=sys.stderr)
                elif aux:
                    print(aux, end='', flush=True, file=sys.stderr)
                else:
                    raise DockerBuildException(parse_msg)
    yield
    if remove_image:
        docker_client.api.remove_image(image_tag)
