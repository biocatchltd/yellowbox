import io
from contextlib import contextmanager
from functools import partial
from os import PathLike
import os
from typing import Collection, Dict, Generator, IO, TypeVar, Union, Sequence

from docker import DockerClient
from docker.errors import ImageNotFound
from docker.models.containers import Container
from docker.models.networks import Network
from tempfile import TemporaryFile, NamedTemporaryFile
import shutil
import weakref
from requests import HTTPError
import tarfile

_DEFAULT_TIMEOUT = 10

_T = TypeVar("_T")
_CT = TypeVar("_CT", bound=Container)
_Gen = Generator[_T, None, None]


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


def is_alive(container: Container) -> bool:
    container.reload()
    return container.status.lower() not in ('exited', 'stopped')


@contextmanager
def killing(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT,
            signal: str = 'SIGKILL') -> _Gen[_CT]:
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


def create_and_pull(docker_client: DockerClient, image, command=None, **kwargs) -> Container:
    try:
        return docker_client.containers.create(image=image, command=command, **kwargs)
    except ImageNotFound:
        docker_client.images.pull(image, platform=None)
        return docker_client.containers.create(image=image, command=command, **kwargs)


def is_removed(container: Container):
    try:
        container.reload()
    except HTTPError:
        return True
    return False


def download_file(container: Container, path: PathLike[str]) -> IO[bytes]:
    """Read a file from the given container"""
    iterator = container.get_archive(os.fspath(path), chunk_size=None)  # noqa

    # Finalizer ensures temporary file will close and be removed.
    temp_file = TemporaryFile("w+b")

    for chunk in iterator:
        temp_file.write(chunk)
    temp_file.seek(0)

    tar_file = tarfile.open(fileobj=temp_file)
    member = tar_file.next()
    return tar_file.extractfile(member)


def upload_file(container: Container, path: PathLike[str], data: bytes = None,
                fileobj: IO[bytes] = None) -> None:
    if data is fileobj is None:
        raise TypeError("data or fileobj must be set.")

    if data is not None is not fileobj:
        raise TypeError("Can't set both data and fileobj.")

    filename = os.path.basename(path)

    tar_data = _create_tar(filename, data, fileobj)

    container.put_archive(os.path.dirname(path), tar_data)


def _create_tar(filename, data=None, fileobj=None) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as tar:
        if data is not None:
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        else:
            try:
                tarinfo = tar.gettarinfo(arcname=filename, fileobj=fileobj)
                tar.addfile(tarinfo, fileobj)
            except (OSError, AttributeError):
                with TemporaryFile("w+b") as temp_file:
                    shutil.copyfileobj(fileobj, temp_file)
                    temp_file.seek(0)
                    temp_file.flush()
                    tarinfo = tar.gettarinfo(arcname=filename, fileobj=temp_file)  # noqa
                    tar.addfile(tarinfo, temp_file)
    return output.getvalue()

