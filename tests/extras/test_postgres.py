from pytest import mark, fixture
from sqlalchemy import Column, Integer, MetaData, String, Table, select, create_engine

from tests.util import unique_name_generator
from yellowbox import connect, temp_network
from yellowbox.containers import upload_file
from yellowbox.extras.postgresql import POSTGRES_INTERNAL_PORT, PostgreSQLService
from yellowbox.utils import docker_host_name


@mark.parametrize('spinner', [True, False])
def test_make_pg(docker_client, spinner):
    with PostgreSQLService.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_local_connection_async(docker_client):
    service: PostgreSQLService
    async with PostgreSQLService.arun(docker_client) as service:
        with service.connection() as connection:
            connection.execute("""
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """)
            connection.execute("""
            DELETE FROM foo WHERE x = 10;
            """)

        with service.connection() as connection:
            results = connection.execute("""
            SELECT x, y FROM foo WHERE y like 't%%'
            """)
            vals = [row['x'] for row in results]
            assert vals == [2, 3]


@fixture(scope='module')
def service(docker_client):
    with PostgreSQLService.run(docker_client, spinner=False) as service:
        yield service

db_name = fixture(unique_name_generator())

@fixture
def db(service, db_name):
    with service.database(db_name) as db:
        yield db

@fixture
def engine(db):
    engine = create_engine(db.local_connection_string())
    yield engine
    engine.dispose()

def test_local_connection(engine):
    with engine.connect() as connection:
        connection.execute("""
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """)
        connection.execute("""
        DELETE FROM foo WHERE x = 10;
        """)

    with engine.connect() as connection:
        results = connection.execute("""
        SELECT x, y FROM foo WHERE y like 't%%'
        """)
        vals = [row['x'] for row in results]
        assert vals == [2, 3]


def test_sibling(docker_client, create_and_pull, engine, service, db_name):
    with engine.connect() as connection:
        connection.execute("""
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """)

    container = create_and_pull(
        docker_client,
        "postgres:latest",
        f'psql -h {docker_host_name} -p {service.external_port()} -U {service.user} -d {db_name}'
        " -c 'DELETE FROM foo WHERE x < 3'",
        environment={'PGPASSWORD': service.password},
        detach=True,
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0

    with engine.connect() as connection:
        results = connection.execute("""SELECT y from foo""")
        vals = [row['y'] for row in results]
    assert vals == ['three', 'ten']


def test_sibling_network(docker_client, create_and_pull, engine, service, db_name):
    with temp_network(docker_client) as network, \
            connect(network, service) as service_alias:
        with engine.connect() as connection:
            connection.execute("""
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """)

        container = create_and_pull(
            docker_client,
            "postgres:latest",
            f'psql -h {service_alias[0]} -p {POSTGRES_INTERNAL_PORT} -U {service.user} -d {db_name}'
            " -c 'DELETE FROM foo WHERE x < 3'",
            environment={'PGPASSWORD': service.password},
            detach=True,
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0

        with engine.connect() as connection:
            results = connection.execute("SELECT y from foo")
            vals = [row['y'] for row in results]
        assert vals == ['three', 'ten']


def test_alchemy_usage(docker_client, engine):
    table = Table('foo', MetaData(),
                  Column('x', Integer),
                  Column('y', String))

    with engine.connect() as connection:
        connection.execute("""
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """)
        results = connection.execute(select([table.c.x]).where(table.c.y.like('t%')))
        vals = [row['x'] for row in results]
    assert vals == [2, 3, 10]


def test_remote_connection_string(docker_client, create_and_pull, service, engine, db):
    with temp_network(docker_client) as network, \
            connect(network, service) as service_alias:
        with engine.connect() as connection:
            connection.execute("""
            CREATE TABLE foo (x INTEGER, y TEXT);
            INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
            """)
        conn_string = db.container_connection_string(service_alias[0])
        container = create_and_pull(
            docker_client,
            "python:latest",
            'sh -c "pip install sqlalchemy psycopg2 && python ./main.py"',
            detach=True,
        )
        upload_file(
            container, './main.py',
            bytes(
                "import sqlalchemy as sa;"
                f"e = sa.create_engine('{conn_string}');"
                "e.execute('DELETE FROM foo WHERE x < 3');",
                'ascii')
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0

        with engine.connect() as connection:
            results = connection.execute("SELECT y from foo")
            vals = [row['y'] for row in results]
        assert vals == ['three', 'ten']


def test_remote_connection_string_host(docker_client, create_and_pull, service, engine, db):
    with engine.connect() as connection:
        connection.execute("""
        CREATE TABLE foo (x INTEGER, y TEXT);
        INSERT INTO foo VALUES (1,'one'), (2, 'two'), (3, 'three'), (10, 'ten');
        """)
    conn_string = db.host_connection_string()
    container = create_and_pull(
        docker_client,
        "python:latest",
        'sh -c "pip install sqlalchemy psycopg2 && python ./main.py"',
        detach=True,
    )
    upload_file(
        container, './main.py',
        bytes(
            "import sqlalchemy as sa;"
            f"e = sa.create_engine('{conn_string}');"
            "e.execute('DELETE FROM foo WHERE x < 3');",
            'ascii')
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0

    with engine.connect() as connection:
        results = connection.execute("SELECT y from foo")
        vals = [row['y'] for row in results]
    assert vals == ['three', 'ten']


def test_mk_db(docker_client):
    with PostgreSQLService.run(docker_client, default_db='foo') as service:
        assert service.database_exists('foo')
        assert not service.database_exists('bar')
        with service.database('bar'):
            assert service.database_exists('foo')
            assert service.database_exists('bar')
        assert service.database_exists('foo')
        assert not service.database_exists('bar')
