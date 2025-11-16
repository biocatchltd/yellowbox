from abc import ABC, abstractmethod
from asyncio import get_running_loop
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager, nullcontext
from functools import partial
from typing import ContextManager, TypeVar

from docker import DockerClient
from docker.models.containers import Container
from docker.models.networks import Network
from typing_extensions import Self

import yellowbox.networks as networks_mod
from yellowbox.containers import _DEFAULT_TIMEOUT, get_aliases, is_alive, is_removed
from yellowbox.retry import RetrySpec
from yellowbox.service import YellowService
from yellowbox.utils import _SPINNER_SUCCESSMSG, _get_spinner


class ContainerService(YellowService):
    def __init__(self, containers: Sequence[Container], remove=True):
        """
        Notes:
             The containers should be ordered so that it is safe to start them in order, and to re
        """
        self.containers = containers
        self.remove = remove

    @abstractmethod
    def start(self, retry_spec: RetrySpec | None = None):
        """
        Start the service. Wait for startup by repeatedly attempting an operation until success

        Args:
            retry_spec: The specifications for the repeated attempts. If not provided,
             a predefined default RetrySpec should be used.

        Returns:
            self, for usage as a context manager.

        Notes:
            This method should block until the service is fully operational.

        """
        for c in self.containers:
            if c.status.lower() == "started":
                continue
            c.start()
            c.reload()
        return super().start()

    def stop(self, signal="SIGTERM"):
        for c in reversed(self.containers):
            if not is_alive(c):
                continue
            c.kill(signal)
            c.wait(timeout=_DEFAULT_TIMEOUT)
            c.reload()
            if self.remove:
                c.remove(v=True)

    def is_alive(self):
        return all(is_alive(c) for c in self.containers)

    @property
    def _endpoint_containers(self) -> Sequence[Container]:
        return self.containers

    def connect(self, network: Network):
        """
        Add the service to an external docker network.
        """
        for ec in self._endpoint_containers:
            network.connect(ec)
            ec.reload()

    def disconnect(self, network: Network, **kwargs):
        """
        Remove the service from an external docker network.

        Note: Implementors should take care not to disconnect removed containers.
        """
        for ec in reversed(self._endpoint_containers):
            if not is_removed(ec):
                network.disconnect(ec, **kwargs)
                ec.reload()


class SingleEndpointService(ContainerService):
    @property
    @abstractmethod
    def _single_endpoint(self) -> Container:
        pass

    @property
    def _endpoint_containers(self) -> Sequence[Container]:
        return (self._single_endpoint,)

    def connect(self, network: Network, **kwargs) -> Sequence[str]:
        network.connect(self._single_endpoint, **kwargs)
        self._single_endpoint.reload()
        return get_aliases(self._single_endpoint, network)

    def disconnect(self, network: Network, **kwargs):
        if not is_removed(self._single_endpoint):
            network.disconnect(self._single_endpoint, **kwargs)
            self._single_endpoint.reload()


class SingleContainerService(SingleEndpointService, ABC):
    def __init__(self, container: Container, **kwargs):
        super().__init__((container,), **kwargs)

    @property
    def container(self):
        return self.containers[0]

    @property
    def _single_endpoint(self) -> Container:
        return self.container


SelfRunMixin = TypeVar("SelfRunMixin", bound="RunMixin")


class RunMixin:
    @classmethod
    def service_name(cls):
        return cls.__name__

    @classmethod
    @contextmanager
    def run(
        cls,
        docker_client: DockerClient,
        *,
        spinner: bool = True,
        retry_spec: RetrySpec | None = None,
        network: Network | None = None,
        **kwargs,
    ) -> Iterator[Self]:
        """
        Args:
            docker_client: a DockerClient instance to use when creating the service
            spinner: whether to use a yaspin spinner
            retry_spec: forwarded to cls.start
            network: connect service to network
            **kwargs: all keyword arguments are forwarded to the class's constructor
        """
        yaspin_spinner = _get_spinner(spinner)
        with yaspin_spinner(f"Fetching {cls.service_name()} ..."):
            service = cls(docker_client, **kwargs)  # type: ignore[call-arg]

        connect_network: ContextManager[None]
        if network:
            connect_network = networks_mod.connect(network, service)
        else:
            connect_network = nullcontext()

        with connect_network:
            with yaspin_spinner(f"Waiting for {cls.service_name()} to start..."):
                service.start(retry_spec=retry_spec)  # type: ignore[attr-defined]
            with service:  # type: ignore[attr-defined]
                yield service


SelfARunMixin = TypeVar("SelfARunMixin", bound="AsyncRunMixin")


class AsyncRunMixin(ABC):
    @classmethod
    def service_name(cls):
        return cls.__name__

    @abstractmethod
    async def astart(self, retry_spec: RetrySpec | None = None) -> None:
        """
        Start the service synchronously, but block and wait for startup asynchronously.
        """

    async def astop(self, *args, **kwargs) -> None:
        """
        Stop the service synchronously, but block and wait for shutdown asynchronously.
        """
        loop = get_running_loop()
        func = partial(self.stop, *args, **kwargs)  # type: ignore[attr-defined]
        await loop.run_in_executor(None, func)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.astop()

    @classmethod
    @asynccontextmanager
    async def arun(
        cls,
        docker_client: DockerClient,
        *,
        verbose: bool = True,
        retry_spec: RetrySpec | None = None,
        network: Network | None = None,
        **kwargs,
    ) -> AsyncIterator[Self]:
        """
        Same as RunMixin.run, but waits for startup asynchronously.

        Args:
            docker_client: a DockerClient instance to use when creating the service
            verbose: whether to print progress information when setting up the service
            retry_spec: forwarded to cls.start
            network: connect service to network
            **kwargs: all keyword arguments are forwarded to the class's constructor
        """

        yaspin_spinner = _get_spinner(verbose)
        with yaspin_spinner(f"Fetching {cls.service_name()} ..."):
            service = cls(docker_client, **kwargs)  # type: ignore[call-arg]

        connect_network: ContextManager[None]
        if network:
            connect_network = networks_mod.connect(network, service)
        else:
            connect_network = nullcontext()

        with connect_network:
            if verbose:
                print(f".   Waiting for {cls.service_name()} to start...")
            await service.astart(retry_spec=retry_spec)
            if verbose:
                print(f"{_SPINNER_SUCCESSMSG} {cls.service_name()} started successfully")
            async with service:
                yield service
