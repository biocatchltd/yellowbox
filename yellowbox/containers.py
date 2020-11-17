from __future__ import annotations

import io
import os
import shutil
import stat
import tarfile
from contextlib import contextmanager
from os import PathLike
from tempfile import TemporaryFile
from typing import Dict, Generator, IO, TypeVar, Union, Sequence, cast

import docker
from docker import DockerClient
from docker.errors import ImageNotFound
from docker.models.containers import Container
from docker.models.networks import Network
from requests import HTTPError

__all__ = ['get_ports', 'get_aliases', 'is_alive', 'is_removed', 'killing', 'create_and_pull',
           'download_file', 'upload_file', 'SafeContainerCreator']

_DEFAULT_TIMEOUT = 10

_T = TypeVar("_T")
_CT = TypeVar("_CT", bound=Container)


def get_ports(container: Container) -> Dict[int, int]:
    """Get the exposed (published) ports of a given container

    Useful for when the ports are assigned dynamically.

    Example:
        >>> c = Container("redis:latest", publish_all_ports=True)
        >>> c.run()
        >>> c.reload()  # Must reload to get updated config.
        >>> ports = get_ports(c)
        >>> ports[6379]  # Random port assigned to 6379 inside the container
        1234

    Note: Container must be up and running. To make sure data is up-to-date,
    make sure you .reload() the container before attempting to fetch the ports.

    Args:
        container: Docker container.

    Returns:
        Port mapping {internal_container_port: external_host_port}.
    """
    # todo this probably won't work for multi-network containers
    ports = {}
    portmap = container.attrs["NetworkSettings"]["Ports"]
    for port, external_address in portmap.items():
        # Filter out unpublished ports.
        if external_address is None:
            continue

        assert len(external_address) > 0

        external_port = int(external_address[0]["HostPort"])

        port, *_ = port.partition("/")  # Strip out type (tcp, udp, ...)
        ports[int(port)] = int(external_port)

    return ports


def get_aliases(container: Container, network: Union[str, Network]) -> Sequence[str]:
    if not isinstance(network, str):
        network = network.name
    return container.attrs["NetworkSettings"]["Networks"][network]["Aliases"]


def short_id(container: Container) -> str:
    """Get the short 12-character id of a container

    By default, the short 12-character id is used as a network alias in all
    of the networks connected to the container.

    Args:
        container: Docker container to retrieve ID from.

    Returns:
        12 character string.
    """
    return container.id[:12]


def is_alive(container: Container) -> bool:
    if is_removed(container):
        return False
    return container.status.lower() not in ('exited', 'stopped')


@contextmanager
def killing(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT,
            signal: str = 'SIGKILL') -> Generator[_CT, None, None]:
    """A context manager that kills a docker container upon completion.

    Example:
        container = DockerContainer(...)
        with killing(container):
            ...
        # Container is now killed with SIGKILL

    Args:
        container: Container to kill upon completion
        timeout: Time to wait for container to be killed after sending a signal.
        Defaults to 10 seconds.
        signal: The signal to send to the container.

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield container
    finally:
        if is_alive(container):
            container.kill(signal)
            container.wait(timeout=timeout)


def create_and_pull(docker_client: DockerClient, image: str, *args, **kwargs) -> Container:
    """
    Create a docker container, pulling the image if necessary.
    Args:
        docker_client: the docker client to use.
        image: the image name to create
        *args: additional arguments forwarded to ``docker_client.containers.create``
        **kwargs: additional arguments forwarded to ``docker_client.containers.create``

    Returns:
        A non-started container.

    Note:
        Due to inconsistent behaviour of docker's "pull" command across
        platforms, this function will raise an error if no tag is specified
    """
    name, _, tag = image.partition(":")
    if not tag:
        raise ValueError('the image name must contain a tag')
    try:
        ret = docker_client.containers.create(image, *args, **kwargs)
    except ImageNotFound:
        docker_client.images.pull(image, platform=None)
        ret = docker_client.containers.create(image, *args, **kwargs)
    return ret


def is_removed(container: Container):
    try:
        container.reload()
    except HTTPError:
        return True
    return False


def download_file(container: Container, path: Union[str, PathLike[str]]
                  ) -> IO[bytes]:
    """Download a file from the given container

    Args:
        container: Docker container at any state.
        path: File path.

    Raises:
        FileNotFoundError: Path was not found.
        IsADirectoryError: Path is not a regular file.
    """
    realpath = os.fspath(path)
    try:
        iterator, stats = container.get_archive(realpath, chunk_size=None)  # noqa
    except docker.errors.NotFound:
        exc = FileNotFoundError(realpath)
        exc.filename = realpath
        raise exc

    if stat.S_ISDIR(stats["mode"]):
        exc = IsADirectoryError(path)
        exc.filename = realpath
        raise exc

    # Finalizer ensures temporary file will close and be removed.
    temp_file = TemporaryFile("w+b")

    for chunk in iterator:
        temp_file.write(chunk)
    temp_file.seek(0)

    tar_file = tarfile.open(fileobj=temp_file)
    member = tar_file.next()
    return cast('IO[bytes]', tar_file.extractfile(member))


def upload_file(container: Container, path: Union[str, PathLike[str]],
                data: bytes = None, fileobj: IO[bytes] = None) -> None:
    """Upload a file to the given container

    Args:
        container: Docker container.
        path: Path to upload the file to.
        data: Bytes of data to upload. Cannot be set with fileobj.
        fileobj: File object to uplaod. Cannot be set with data.
    """
    if data is fileobj is None:
        raise TypeError("data or fileobj must be set.")

    if data is not None is not fileobj:
        raise TypeError("Can't set both data and fileobj.")

    filename = os.path.basename(path)

    tar_data = _create_tar(filename, data, fileobj)

    container.put_archive(os.path.dirname(path), tar_data)


def _create_tar(filename, data=None, fileobj=None) -> bytes:
    """Create a tarfile made of the given data

    Args:
        filename: Name of the file to create inside the tar
        data: Data of the file. Cannot exist with fileobj.
        fileobj: File object. Cannot exist with data.

    Returns:
        Bytes of a tarfile, containing the given file.
    """
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as tar:
        if data is not None:
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        else:
            try:
                # Attempt to extract info (such as size) from file object
                tarinfo = tar.gettarinfo(arcname=filename, fileobj=fileobj)
                tar.addfile(tarinfo, fileobj)
            except (OSError, AttributeError):
                # Failed to extract info, writing and reading from temp file.
                with TemporaryFile("w+b") as temp_file:
                    shutil.copyfileobj(fileobj, temp_file)
                    temp_file.seek(0)
                    temp_file.flush()
                    tarinfo = tar.gettarinfo(arcname=filename, fileobj=temp_file)  # noqa
                    tar.addfile(tarinfo, temp_file)
    return output.getvalue()


class SafeContainerCreator:
    """
    A class that can safely pull and create multiple containers in succession, where if one fails, all the previous
     ones are removed
    """
    def __init__(self, client: DockerClient):
        self.client = client
        self.created = []

    def create_and_pull(self, image, command=None, **kwargs):
        try:
            container = create_and_pull(self.client, image, command, **kwargs)
        except Exception:
            for container in reversed(self.created):
                container.remove(v=True)
            raise
        self.created.append(container)
        return container
