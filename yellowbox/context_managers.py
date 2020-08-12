from contextlib import contextmanager, nullcontext
from typing import Generator, TypeVar

from docker.models.containers import Container as DockerContainer
from docker.models.networks import Network as DockerNetwork

_T = TypeVar("_T")
_CT = TypeVar("_CT", bound=DockerContainer)
_NT = TypeVar("_NT", bound=DockerNetwork)
_Gen = Generator[_T, None, None]

_DEFAULT_TIMEOUT = 10


@contextmanager
def killing(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT) -> _Gen[_CT]:
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

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield container
    finally:
        if container.status.lower() not in ('exited', 'stopped'):
            container.kill('SIGKILL')
            container.wait(timeout=timeout)


@contextmanager
def terminating(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT) -> _Gen[_CT]:
    """A context manager that terminates a docker container upon completion.

    Example:
        container = DockerContainer(...)
        with terminating(container):
            ...
        # Container is now killed with SIGTERM (equal to ctrl+c in most places).

    Args:
        container: Container to terminate upon completion
        timeout: Time to wait for container to be terminated after sending a
        signal. Defaults to 10 seconds.

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield container
    finally:
        if container.status.lower() not in ('exited', 'stopped'):
            container.kill('SIGTERM')
            container.wait(timeout=timeout)


@contextmanager
def disconnecting(network: _NT) -> _Gen[_NT]:
    """A context manager that disconnects a docker network upon completion.

    Example:
        network = DockerNetwork(...)
        with disconnecting(network):
            ...
        # Network is now disconnected from all containers and is removed
        # from docker.

    Args:
        network: Network to disconnect upon completion.

    Returns:
        A context manager to be used in a 'with' statement.
    """
    try:
        yield network
    finally:
        for container in network.containers:
            network.disconnect(container)
        network.remove()


try:
    from yaspin import yaspin
except ImportError:
    spinner = nullcontext
else:
    @contextmanager
    def spinner(text):
        with yaspin(text=text) as spinner:
            try:
                yield
            except Exception:
                spinner.fail("💥 ")
                raise
            spinner.ok("✅ ")
