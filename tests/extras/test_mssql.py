from pytest import mark
from sqlalchemy import Column, Integer, MetaData, String, Table, select

from yellowbox import connect, temp_network
from yellowbox.containers import upload_file
from yellowbox.extras.mssql import MSSQLService
from yellowbox.utils import docker_host_name


@mark.parametrize('spinner', [True])
def test_make_mssql(docker_client, spinner):
    with MSSQLService.run(docker_client, spinner=spinner):
        input('!!! ready')
