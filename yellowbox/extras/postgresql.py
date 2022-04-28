from typing import Optional, Union, Mapping

from deprecated import deprecated
from docker import DockerClient
from sqlalchemy import create_engine

from yellowbox.containers import create_and_pull
from yellowbox.extras.sql_base import SQLServiceMixin
from yellowbox.subclasses import SingleContainerService

__all__ = ['PostgreSQLService', 'POSTGRES_INTERNAL_PORT']

POSTGRES_INTERNAL_PORT = 5432


class PostgreSQLService(SQLServiceMixin, SingleContainerService):
    """
    A postgresSQL service
    """

    INTERNAL_PORT = POSTGRES_INTERNAL_PORT
    DIALECT = 'postgresql'

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
        ), default_database=default_db, **kwargs)

    def userpass(self):
        return self.user, self.password

    def local_connection_string(self, dialect: str = ..., driver: str = None, database: Optional[str] = None,
                                options: Union[None, str, Mapping[str, str]] = None):
        database = database or self.default_db
        return super().local_connection_string(dialect, driver, database=database, options=options)

    def container_connection_string(self, hostname: str, dialect: str = 'postgresql', driver: str = None,
                                    database: str = None, options: Union[None, str, Mapping[str, str]] = None):
        database = database or self.default_db
        return super().container_connection_string(hostname, dialect, driver, database=database, options=options)

    def host_connection_string(self, dialect: str = 'postgresql', driver: str = None, database: str = None,
                               options: Union[None, str, Mapping[str, str]] = None):
        database = database or self.default_db
        return super().host_connection_string(dialect, driver, database=database, options=options)

    @deprecated(version='0.7.2', reason='Use sqlalchemy.create_engine(service.local_connection_string()) instead')
    def engine(self, **kwargs):
        """
        Create an sqlalchemy Engine connected to the service's default db.
        """
        cs = self.local_connection_string()
        return create_engine(cs, **kwargs)

    @deprecated(version='0.7.2',
                reason='Use sqlalchemy.create_engine(service.local_connection_string()).connect() instead')
    def connection(self, **kwargs):
        """
        Create an sqlalchemy Connection connected to the service's default db.
        """
        return self.engine().connect(**kwargs)

    def stop(self, signal='SIGINT'):
        # change in default
        return super().stop(signal)
