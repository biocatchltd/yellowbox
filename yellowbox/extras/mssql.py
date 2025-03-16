from typing import Any, Dict, Optional

from docker import DockerClient

from yellowbox.containers import create_and_pull_with_defaults
from yellowbox.extras.sql_base import ConnectionOptions, SQLService
from yellowbox.subclasses import SingleContainerService

__all__ = ["MSSQLService"]


class MSSQLService(SQLService, SingleContainerService):
    """
    A postgresSQL service
    """

    INTERNAL_PORT = 1433
    DIALECT = "mssql"

    def __init__(
        self,
        docker_client: DockerClient,
        image="mcr.microsoft.com/mssql/server:latest",
        *,
        admin_password: str = "Swordfish1!",
        product: str = "Developer",
        accept_eula: Optional[str] = None,
        local_driver: Optional[str] = None,
        local_options: Optional[ConnectionOptions] = None,
        container_create_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.admin_password = admin_password
        if accept_eula is None:
            if product == "Developer":
                accept_eula = "y"
            else:
                raise ValueError(f"accept_eula must be set for product {product}")

        if local_driver in (None, "pyodbc") and local_options is None:
            try:
                import pyodbc
            except ImportError as e:
                raise ImportError("pyodbc is required if no other driver is specified") from e
            available_drivers = pyodbc.drivers()
            if not available_drivers:
                raise ValueError(
                    "No odbc drivers found, install drivers here:"
                    " https://docs.microsoft.com/en-us/sql/connect/odbc/"
                    "download-odbc-driver-for-sql-server"
                )
            local_options = {
                "TrustServerCertificate": "yes",
                "driver": available_drivers[0],
            }

        super().__init__(
            create_and_pull_with_defaults(
                docker_client,
                image,
                _kwargs=container_create_kwargs,
                publish_all_ports=True,
                detach=True,
                environment={"ACCEPT_EULA": accept_eula, "SA_PASSWORD": admin_password, "MSSQL_PID": product},
            ),
            default_database="master",
            local_driver=local_driver,
            local_options=local_options,
            **kwargs,
        )

    def userpass(self):
        return "sa", self.admin_password

    def stop(self, signal="SIGKILL"):
        # change in default
        return super().stop(signal)
