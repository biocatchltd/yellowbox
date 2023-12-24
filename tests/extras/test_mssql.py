from pytest import fixture, mark
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select, text

from tests.util import unique_name_generator
from yellowbox.containers import upload_file
from yellowbox.extras.mssql import MSSQLService
from yellowbox.networks import connect, temp_network
from yellowbox.utils import docker_host_name


@mark.parametrize("spinner", [True, False])
def test_make_mssql(docker_client, spinner):
    with MSSQLService.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_local_connection_async(docker_client):
    service: MSSQLService
    async with MSSQLService.arun(docker_client) as service:
        db = service.database("foobar")
        engine = create_engine(db.local_connection_string())
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """
                )
            )
            connection.execute(
                text(
                    """
            DELETE FROM foo WHERE x = 10;
            """
                )
            )

        with engine.begin() as connection:
            results = connection.execute(
                text(
                    """
            SELECT x, y FROM foo WHERE y like 't%%'
            """
                )
            )
            vals = [row["x"] for row in results.mappings()]
            assert vals == [2, 3]


@fixture(scope="module")
def service(docker_client):
    with MSSQLService.run(docker_client, spinner=False) as service:
        yield service


db_name = fixture(unique_name_generator())


@fixture()
def db(service, db_name):
    with service.database(db_name) as db:
        yield db


@fixture()
def engine(db):
    engine = create_engine(db.local_connection_string())
    yield engine
    engine.dispose()


def test_mk_db(service, db_name):
    assert not service.database_exists(db_name)
    with service.database(db_name):
        assert service.database_exists(db_name)
    assert not service.database_exists(db_name)


def test_local_connection(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """
            )
        )
        connection.execute(
            text(
                """
        DELETE FROM foo WHERE x = 10;
        """
            )
        )

    with engine.begin() as connection:
        results = connection.execute(
            text(
                """
        SELECT x, y FROM foo WHERE y like 't%%'
        """
            )
        )
        vals = [row["x"] for row in results.mappings()]
        assert vals == [2, 3]


def test_sibling(service, db_name, engine, create_and_pull, docker_client):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """
            )
        )

    container = create_and_pull(
        docker_client,
        "fabiang/sqlcmd:latest",
        f"-S {docker_host_name},{service.external_port()} -U sa -P {service.admin_password} -d {db_name} -C"
        " -Q 'DELETE FROM foo WHERE x < 3'",
        detach=True,
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0

    with engine.begin() as connection:
        results = connection.execute(text("""SELECT y FROM foo"""))
        vals = [row["y"] for row in results.mappings()]
    assert vals == ["three", "ten"]


def test_sibling_network(service, db_name, engine, create_and_pull, docker_client):
    with temp_network(docker_client) as network, connect(network, service) as service_alias:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """
                )
            )

        container = create_and_pull(
            docker_client,
            "fabiang/sqlcmd:latest",
            f"-S {service_alias[0]},{service.INTERNAL_PORT} -U sa -P {service.admin_password} -d {db_name} -C"
            " -Q 'DELETE FROM foo WHERE x < 3'",
            detach=True,
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0

        with engine.begin() as connection:
            results = connection.execute(text("SELECT y from foo"))
            vals = [row["y"] for row in results.mappings()]
        assert vals == ["three", "ten"]


def test_alchemy_usage(service, engine):
    table = Table("foo", MetaData(), Column("x", Integer), Column("y", String))

    with engine.begin() as connection:
        connection.execute(
            text(
                """
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """
            )
        )
        results = connection.execute(select(table.c.x).where(table.c.y.like("t%")))
        vals = [row["x"] for row in results.mappings()]
    assert vals == [2, 3, 10]


def test_remote_connection_string(service, db, engine, create_and_pull, docker_client):
    with temp_network(docker_client) as network, connect(network, service) as service_alias:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """
                )
            )
        conn_string = db.container_connection_string(
            service_alias[0],
            options={
                "TrustServerCertificate": "yes",
                "driver": "ODBC Driver 17 for SQL Server",
            },
        )
        container = create_and_pull(
            docker_client,
            "laudio/pyodbc:latest",
            'sh -c "pip install sqlalchemy==1.4.46 pyodbc && python ./main.py"',
            detach=True,
        )
        upload_file(
            container,
            "./main.py",
            bytes(
                "import sqlalchemy as sa;"
                f"e = sa.create_engine('{conn_string}');"
                "e.execute('DELETE FROM foo WHERE x < 3');",
                "ascii",
            ),
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0

        with engine.begin() as connection:
            results = connection.execute(text("SELECT y from foo"))
            vals = [row["y"] for row in results.mappings()]
        assert vals == ["three", "ten"]


def test_remote_connection_string_host(service, db, engine, create_and_pull, docker_client):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """
            )
        )
    conn_string = db.host_connection_string(
        options={
            "TrustServerCertificate": "yes",
            "driver": "ODBC Driver 17 for SQL Server",
        }
    )
    container = create_and_pull(
        docker_client,
        "laudio/pyodbc:latest",
        'sh -c "pip install sqlalchemy==1.4.46 pyodbc && python ./main.py"',
        detach=True,
    )
    upload_file(
        container,
        "./main.py",
        bytes(
            "import sqlalchemy as sa;"
            f"e = sa.create_engine('{conn_string}');"
            "e.execute('DELETE FROM foo WHERE x < 3');",
            "ascii",
        ),
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0

    with engine.begin() as connection:
        results = connection.execute(text("SELECT y from foo"))
        vals = [row["y"] for row in results.mappings()]
    assert vals == ["three", "ten"]
