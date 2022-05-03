from __future__ import annotations

from abc import abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, ContextManager, Mapping, Optional, Tuple, Union

from sqlalchemy import create_engine
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy_utils import create_database, database_exists, drop_database

from yellowbox import RetrySpec
from yellowbox.containers import get_ports
from yellowbox.subclasses import AsyncRunMixin, RunMixin, SingleEndpointService
from yellowbox.utils import docker_host_name

if TYPE_CHECKING:  # pragma: no cover
    class AsDefault(Enum):
        as_default = auto()

    as_default = AsDefault.as_default
else:
    as_default = object()

ConnectionOptions = Union[str, Mapping[str, str]]


class Database(ContextManager['Database']):
    # represents a database that is ensured to exist
    def __init__(self, name: str, owner: SQLService):
        self.name = name
        self.owner = owner

    def local_connection_string(self, dialect: Union[str, AsDefault] = as_default, driver: Optional[str] = None,
                                options: Union[ConnectionOptions, None, AsDefault] = as_default):
        return self.owner.local_connection_string(dialect, driver, database=self.name, options=options)

    def container_connection_string(self, hostname: str, dialect: Union[str, AsDefault] = as_default,
                                    driver: Optional[str] = None, options: Optional[ConnectionOptions] = None):
        return self.owner.container_connection_string(hostname, dialect, driver, database=self.name, options=options)

    def host_connection_string(self, dialect: Union[str, AsDefault] = as_default, driver: Optional[str] = None,
                               options: Optional[ConnectionOptions] = None):
        return self.owner.host_connection_string(dialect, driver, database=self.name, options=options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.owner.drop_database(self.name)


def _options_to_string(options: Optional[ConnectionOptions]) -> str:
    if options is None:
        return ''
    if isinstance(options, Mapping):
        return '?' + '&'.join(f"{k}={str(v).replace(' ', '+')}" for k, v in options.items())
    if not options.startswith('?'):
        return '?' + options
    return options


class SQLService(SingleEndpointService, RunMixin, AsyncRunMixin, ):
    LOCAL_HOSTNAME = 'localhost'
    INTERNAL_PORT: int
    DIALECT: str
    DEFAULT_START_RETRYSPEC = RetrySpec(attempts=20)

    def __init__(self, *args, local_driver: Optional[str] = None, local_options: Optional[ConnectionOptions] = None,
                 default_database: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_driver = local_driver
        self.local_options = local_options
        self.default_database = default_database

    @abstractmethod
    def userpass(self) -> Tuple[str, str]:
        pass

    def create_database(self, name: str):
        cs = self.local_connection_string(database=name)
        if database_exists(cs):
            raise ValueError(f"Database {name} already exists")
        create_database(cs)

    def drop_database(self, name: str):
        drop_database(self.local_connection_string(database=name))

    def database_exists(self, name: str) -> bool:
        return database_exists(self.local_connection_string(database=name))

    def external_port(self) -> int:
        return get_ports(self._single_endpoint)[self.INTERNAL_PORT]

    def local_connection_string(self, dialect: Union[str, AsDefault] = as_default,
                                driver: Union[str, AsDefault, None] = as_default, *, database: str,
                                options: Union[ConnectionOptions, AsDefault, None] = as_default) -> str:
        """
        Generate an sqlalchemy-style connection string to the database in the service from the docker host.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to.
            options: additional options to pass to the connection string.
        """
        if dialect is as_default:
            dialect = self.DIALECT

        if driver is as_default:
            driver = self.local_driver
        if driver is not None:
            dialect += '+' + driver

        if options is as_default:
            options = self.local_options

        options = _options_to_string(options)

        return f'{dialect}://{":".join(self.userpass())}@{self.LOCAL_HOSTNAME}:{self.external_port()}/' \
               f'{database}{options}'

    def container_connection_string(self, hostname: str, dialect: Union[str, AsDefault] = as_default,
                                    driver: Optional[str] = None, *, database: str,
                                    options: Optional[ConnectionOptions] = None) -> str:
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
        if dialect is as_default:
            dialect = self.DIALECT

        if driver is not None:
            dialect += '+' + driver

        options = _options_to_string(options)

        return f'{dialect}://{":".join(self.userpass())}@{hostname}:{self.INTERNAL_PORT}/' \
               f'{database}{options}'

    def host_connection_string(self, dialect: Union[str, AsDefault] = as_default, driver: Optional[str] = None,
                               *, database: str, options: Optional[ConnectionOptions] = None) -> str:
        """
        Generate an sqlalchemy-style connection string to the database in the service from another container.
        Args:
            dialect: The dialect of the sql server.
            driver: additional driver for sqlalchemy to use.
            database: the name of the database to connect to.
            options: additional options to pass to the connection string.
        """
        if dialect is as_default:
            dialect = self.DIALECT

        if driver is not None:
            dialect += '+' + driver

        options = _options_to_string(options)

        return f'{dialect}://{":".join(self.userpass())}@{docker_host_name}:{self.external_port()}/' \
               f'{database}{options}'

    def database(self, name: str) -> Database:
        if not self.database_exists(name):
            self.create_database(name)
        return Database(name, self)

    def _connect(self):
        cs = self.local_connection_string(database=self.default_database)
        engine = create_engine(cs)
        with engine.connect():
            return

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start(retry_spec)
        retry_spec = retry_spec or self.DEFAULT_START_RETRYSPEC

        retry_spec.retry(self._connect, (OperationalError, InterfaceError))
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None) -> None:
        super().start(retry_spec)
        retry_spec = retry_spec or self.DEFAULT_START_RETRYSPEC

        await retry_spec.aretry(self._connect, (OperationalError, InterfaceError))
