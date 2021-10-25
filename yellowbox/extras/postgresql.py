from typing import Optional

from docker import DockerClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from yellowbox import RetrySpec, RunMixin
from yellowbox.containers import create_and_pull, get_ports
from yellowbox.subclasses import SingleContainerService

__all__ = ['PostgreSQLService', 'POSTGRES_INTERNAL_PORT']

from yellowbox.utils import docker_host_name

POSTGRES_INTERNAL_PORT = 5432


class PostgreSQLService(SingleContainerService, RunMixin):
    """
    A postgresSQL service
    """

    def __init__(self, docker_client: DockerClient, image='postgres:latest', *, user='postgres',
                 password='guest', default_db: str = None, **kwargs):
        """
        Args:
            user: the Name of the default user for the database
            password: The password of the default user for the database
            default_db: The name of the default database. Defaults to the user name.
        """
        if default_db is None:
            default_db = user

        self.user = user
        self.password = password
        self.default_db = default_db
        super().__init__(create_and_pull(
            docker_client, image, publish_all_ports=True, detach=True, environment={
                'POSTGRES_USER': user,
                'POSTGRES_PASSWORD': password,
                'POSTGRES_DB': default_db
            }
        ), **kwargs)

    def external_port(self):
        return get_ports(self.container)[POSTGRES_INTERNAL_PORT]

    def local_connection_string(self, dialect: str = 'postgresql', driver: str = None, database: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from the docker host.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to. Defaults to the service's default database.
        """
        database = database or self.default_db

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://{self.user}:{self.password}@localhost:{self.external_port()}/{database}'

    def container_connection_string(self, hostname: str, dialect: str = 'postgresql', driver: str = None,
                                    database: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container on a
         common network.
        Args:
            hostname: the alias of the container.
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to. Defaults to the service's default database.
        """
        database = database or self.default_db

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://{self.user}:{self.password}@{hostname}:{POSTGRES_INTERNAL_PORT}/{database}'

    def host_connection_string(self, dialect: str = 'postgresql', driver: str = None, database: str = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to. Defaults to the service's default database.
        """
        database = database or self.default_db

        if driver is not None:
            dialect += '+' + driver

        return f'{dialect}://{self.user}:{self.password}@{docker_host_name}:{self.external_port()}/{database}'

    def engine(self, **kwargs):
        """
        Create an sqlalchemy Engine connected to the service's default db.
        """
        cs = self.local_connection_string()
        return create_engine(cs, **kwargs)

    def connection(self, **kwargs):
        """
        Create an sqlalchemy Connection connected to the service's default db.
        """
        return self.engine().connect(**kwargs)

    def start(self, retry_spec: Optional[RetrySpec] = None):
        retry_spec = retry_spec or RetrySpec(attempts=20)
        super().start(retry_spec)

        def connect():
            with self.connection():
                return

        retry_spec.retry(connect, OperationalError)
        return self

    def stop(self, signal='SIGINT'):
        # change in default
        return super().stop(signal)
