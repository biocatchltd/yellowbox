from __future__ import annotations

from abc import ABC
from typing import Optional, Mapping, Union, Set, ContextManager

from docker.models.containers import Container
from mypy.nodes import abstractmethod

from yellowbox.containers import get_ports
from yellowbox.utils import docker_host_name


class Database(ContextManager['Database']):
    # represents a database that is ensured to exist
    def __init__(self, name: str, owner: SQLServiceMixin):
        self.name = name
        self.owner = owner

    def local_connection_string(self, dialect: str = ..., driver: Optional[str] = None,
                                options: Union[None, str, Mapping[str, str]] = None):
        return self.owner.local_connection_string(dialect, driver, database=self.name, options=options)

    def container_connection_string(self, hostname: str, dialect: str = ..., driver: Optional[str] = None,
                                    options: Union[None, str, Mapping[str, str]] = None):
        return self.owner.container_connection_string(hostname, dialect, driver, database=self.name, options=options)

    def host_connection_string(self, dialect: str = ..., driver: Optional[str] = None,
                               options: Union[None, str, Mapping[str, str]] = None):
        return self.owner.host_connection_string(dialect, driver, database=self.name, options=options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.owner.drop_database(self.name)


def _options_to_string(options: Union[None, str, Mapping[str, str]]) -> str:
    if options is None:
        return ''
    if isinstance(options, Mapping):
        return '?' + '&'.join(f"{k}={str(v).replace(' ', '+')}" for k, v in options.items())
    if not options.startswith('?'):
        return '?' + options
    return options


class SQLServiceMixin(ABC):
    LOCAL_HOSTNAME = 'localhost'
    INTERNAL_PORT: int
    DIALECT: str

    container: Container

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.databases: Set[str] = set()
        # the mixin has the assumption that is aware of all databases in the container i.e. checking for the existance
        # of a database is done by simply checking inclusion in this set

    @abstractmethod
    def username(self) -> str:
        pass

    @abstractmethod
    def password(self) -> str:
        pass

    @abstractmethod
    def create_database(self, name: str):
        self.databases.add(name)

    @abstractmethod
    def drop_database(self, name: str):
        self.databases.remove(name)

    def external_port(self) -> int:
        return get_ports(self.container)[self.INTERNAL_PORT]

    def local_connection_string(self, dialect: str = ..., driver: Optional[str] = None, *, database: str,
                                options: Union[None, str, Mapping[str, str]] = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from the docker host.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to.
            options: additional options to pass to the connection string.
        """
        if dialect is ...:
            dialect = self.DIALECT

        if driver is not None:
            dialect += '+' + driver

        options = _options_to_string(options)

        return f'{dialect}://{self.username()}:{self.password()}@{self.LOCAL_HOSTNAME}:{self.external_port()}/' \
               f'{database}{options}'

    def container_connection_string(self, hostname: str, dialect: str = ..., driver: Optional[str] = None, *,
                                    database: str, options: Union[None, str, Mapping[str, str]] = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container on a
         common network.
        Args:
            hostname: the alias of the container.
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to.
            options: additional options to pass to the connection string.
        """
        if dialect is ...:
            dialect = self.DIALECT

        if driver is not None:
            dialect += '+' + driver

        options = _options_to_string(options)

        return f'{dialect}://{self.username()}:{self.password()}@{hostname}:{self.INTERNAL_PORT}/' \
               f'{database}{options}'

    def host_connection_string(self, dialect: str = ..., driver: Optional[str] = None, *, database: str,
                               options: Union[None, str, Mapping[str, str]] = None):
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to.
            options: additional options to pass to the connection string.
        """
        if dialect is ...:
            dialect = self.DIALECT

        if driver is not None:
            dialect += '+' + driver

        options = _options_to_string(options)

        return f'{dialect}://{self.username()}:{self.password()}@{docker_host_name}:{self.external_port()}/' \
               f'{database}{options}'

    def database(self, name: str) -> Database:
        if name not in self.databases:
            self.create_database(name)
        return Database(name, self)
