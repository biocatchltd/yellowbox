import hvac
from hvac.exceptions import InvalidPath
from pytest import fixture, mark, raises

from tests.util import unique_name_generator
from yellowbox import connect, temp_network
from yellowbox.extras.vault import VaultService


def assert_is_missing(client: hvac.Client, path: str):
    with raises(InvalidPath):
        client.secrets.kv.read_secret(path)


def test_create_vault(docker_client):
    with VaultService.run(docker_client):
        pass


@mark.asyncio
async def test_vault_secrets_async(docker_client):
    async with VaultService.arun(docker_client) as service:
        service.set_secrets({
            'foo': {'smee': {'lee': 23}},
            'tlee/gmoo': {'hero': 'shmero'},
        })
        with service.client() as client:
            assert client.secrets.kv.read_secret('foo')['data']['data'] == {'smee': {'lee': 23}}
            assert client.secrets.kv.read_secret('tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
            assert_is_missing(client, 'tlee')


@fixture(scope='module')
def service(docker_client):
    with VaultService.run(docker_client, spinner=False) as service:
        yield service


secret_prefix = fixture(unique_name_generator())
user_prefix = fixture(unique_name_generator())


def test_vault_secrets(service, secret_prefix):
    service.set_secrets({
        secret_prefix + 'foo': {'smee': {'lee': 23}},
        secret_prefix + 'tlee/gmoo': {'hero': 'shmero'},
    })
    with service.client() as client:
        assert client.secrets.kv.read_secret(secret_prefix + 'foo')['data']['data'] == {'smee': {'lee': 23}}
        assert client.secrets.kv.read_secret(secret_prefix + 'tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
        assert_is_missing(client, secret_prefix + 'tlee')


def test_vault_login(service, secret_prefix, user_prefix):
    service.set_users([(user_prefix + 'james_bond', 'swordfish')])
    service.set_secrets({
        secret_prefix + 'foo': {'smee': {'lee': 23}},
        secret_prefix + 'tlee/gmoo': {'hero': 'shmero'},
    })

    client = hvac.Client(service.local_url())
    client.auth_userpass(user_prefix + 'james_bond', 'swordfish')
    assert client.is_authenticated()

    assert client.secrets.kv.read_secret(secret_prefix + 'foo')['data']['data'] == {'smee': {'lee': 23}}
    assert client.secrets.kv.read_secret(secret_prefix + 'tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
    assert_is_missing(client, secret_prefix + 'tlee')


def test_vault_reuse_policy(service, secret_prefix, user_prefix):
    service.set_users([(user_prefix + 'james_bond', 'swordfish')], policy_name='agents')
    service.set_users([(user_prefix + 'bames_jond', 'swordfish')], policy_name='agents', policy=None)

    service.set_secrets({
        secret_prefix + 'foo': {'smee': {'lee': 23}},
        secret_prefix + 'tlee/gmoo': {'hero': 'shmero'},
    })

    client = hvac.Client(service.local_url())
    client.auth_userpass(user_prefix + 'bames_jond', 'swordfish')
    assert client.is_authenticated()

    assert client.secrets.kv.read_secret(secret_prefix + 'foo')['data']['data'] == {'smee': {'lee': 23}}
    assert client.secrets.kv.read_secret(secret_prefix + 'tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
    assert_is_missing(client, secret_prefix + 'tlee')


def test_vault_clean_secrets(service, secret_prefix):
    service.set_secrets({
        secret_prefix + 'a': {'v': 0},
        secret_prefix + 'a/b': {'v': 0},
        secret_prefix + 'a/b/c': {'v': 0},
        secret_prefix + 'a1/b': {'v': 0},
        secret_prefix + 'a2': {'v': 0},
    })
    with service.client() as client:
        assert client.secrets.kv.read_secret(secret_prefix + 'a/b/c')['data']['data'] == {'v': 0}

    service.clear_secrets()

    with service.client() as client:
        assert_is_missing(client, secret_prefix + 'a')
        assert_is_missing(client, secret_prefix + 'a/b')
        assert_is_missing(client, secret_prefix + 'a/b/c')
        assert_is_missing(client, secret_prefix + 'a1/b')
        assert_is_missing(client, secret_prefix + 'a2')


def test_vault_clean_some_secrets(service, secret_prefix):
    service.set_secrets({
        secret_prefix + 'a': {'v': 0},
        secret_prefix + 'a/b': {'v': 0},
        secret_prefix + 'a/b/c': {'v': 0},
        secret_prefix + 'a1/b': {'v': 0},
        secret_prefix + 'a2': {'v': 0},
    })
    with service.client() as client:
        assert client.secrets.kv.read_secret(secret_prefix + 'a/b/c')['data']['data'] == {'v': 0}

    service.clear_secrets(secret_prefix + 'a/')

    with service.client() as client:
        assert_is_missing(client, secret_prefix + 'a/b')
        assert_is_missing(client, secret_prefix + 'a/b/c')
        assert client.secrets.kv.read_secret(secret_prefix + 'a')['data']['data'] == {'v': 0}
        assert client.secrets.kv.read_secret(secret_prefix + 'a2')['data']['data'] == {'v': 0}


def test_container(service, docker_client, create_and_pull):
    container = create_and_pull(
        docker_client,
        "byrnedo/alpine-curl:latest",
        f'-vvv "{service.container_url()}/v1/sys/health" --fail -X "GET" -H "X-Vault-Token:guest"'
    )
    container.reload()
    assert container.attrs['State']["ExitCode"] == 0


def test_container_same_network(service, docker_client, create_and_pull):
    with temp_network(docker_client) as network, connect(network, service) as aliases:
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv "{service.sibling_container_url(aliases[0])}/v1/sys/health" --fail -X "GET" -H'
            ' "X-Vault-Token:guest"',
            detach=True
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0
