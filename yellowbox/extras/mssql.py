from typing import Optional

from docker import DockerClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from yellowbox import RetrySpec, RunMixin
from yellowbox.containers import create_and_pull, get_ports
from yellowbox.subclasses import AsyncRunMixin, SingleContainerService

__all__ = ['MSSQLService', 'MSSQL_INTERNAL_PORT']

from yellowbox.utils import docker_host_name

MSSQL_INTERNAL_PORT = 1433


class MSSQLService(SingleContainerService, RunMixin, AsyncRunMixin):
    """
    A postgresSQL service
    """

    def __init__(self, docker_client: DockerClient, image='mcr.microsoft.com/mssql/server:latest', *,
                 admin_password: str = 'Swordfish1!', product: str = 'Developer', accept_eula: Optional[str] = None,
                 **kwargs):
        self.admin_password = admin_password
        if accept_eula is None:
            if product == 'Developer':
                accept_eula = 'y'
            else:
                raise ValueError(f'accept_eula must be set for product {product}')
        super().__init__(create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True, environment={
                'ACCEPT_EULA': accept_eula,
                'SA_PASSWORD': admin_password,
                'MSSQL_PID': product
            }
        ), **kwargs)

    def external_port(self):
        return get_ports(self.container)[MSSQL_INTERNAL_PORT]

    def local_connection_string(self, dialect: str = 'mssql', driver: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from the docker host.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
        """

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://sa:{self.admin_password}@127.0.0.1:{self.external_port()}/foobar?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'

    def container_connection_string(self, hostname: str, dialect: str = 'mssql', driver: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container on a
         common network.
        Args:
            hostname: the alias of the container.
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
        """

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://sa:{self.admin_password}@{hostname}:{MSSQL_INTERNAL_PORT}/'

    def host_connection_string(self, dialect: str = 'mssql', driver: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
        """

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://sa:{self.admin_password}@{docker_host_name}:{self.external_port()}/'

    def _connect(self):
        cs = self.local_connection_string()
        try:
            engine = create_engine(cs)
            with engine.connect():
                return
        except Exception as e:
            print(f'!!! {e=}')
            raise

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start(retry_spec)
        retry_spec = retry_spec or RetrySpec(attempts=20)

        retry_spec.retry(self._connect, OperationalError)
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None) -> None:
        super().start(retry_spec)
        retry_spec = retry_spec or RetrySpec(attempts=20)

        await retry_spec.aretry(self._connect, OperationalError)

    def stop(self, signal='SIGINT'):
        # change in default
        return super().stop(signal)
