import json
import sys
from contextlib import contextmanager
from typing import Generator, TypeVar

from docker import DockerClient
from docker.models.containers import Container as DockerContainer
from docker.models.networks import Network as DockerNetwork

_T = TypeVar("_T")
_CT = TypeVar("_CT", bound=DockerContainer)
_NT = TypeVar("_NT", bound=DockerNetwork)
_Gen = Generator[_T, None, None]

_DEFAULT_TIMEOUT = 10


@contextmanager
def killing(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT) -> _Gen[_CT]:
    try:
        yield container
    finally:
        if container.status.lower() not in ('exited', 'stopped'):
            container.kill('SIGKILL')
            container.wait(timeout=timeout)


@contextmanager
def terminating(container: _CT, *, timeout: float = _DEFAULT_TIMEOUT) -> _Gen[_CT]:
    try:
        yield container
    finally:
        if container.status.lower() not in ('exited', 'stopped'):
            container.kill('SIGTERM')
            container.wait(timeout=timeout)


@contextmanager
def disconnecting(network: _NT) -> _Gen[_NT]:
    try:
        yield network
    finally:
        for container in network.containers:
            network.disconnect(container)
        network.remove()


