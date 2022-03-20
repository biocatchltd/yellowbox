import hvac
from hvac.exceptions import InvalidPath
from pytest import mark, raises

from yellowbox import connect, temp_network
from yellowbox.extras.vault import VaultService


def assert_is_missing(client: hvac.Client, path: str):
    with raises(InvalidPath):
        client.secrets.kv.read_secret(path)


def test_create_vault(docker_client):
    with VaultService.run(docker_client):
        pass


def test_vault_secrets(docker_client):
    with VaultService.run(docker_client) as service:
        service.set_secrets({
            'foo': {'smee': {'lee': 23}},
            'tlee/gmoo': {'hero': 'shmero'},
        })
        with service.client() as client:
            assert client.secrets.kv.read_secret('foo')['data']['data'] == {'smee': {'lee': 23}}
            assert client.secrets.kv.read_secret('tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
            assert_is_missing(client, 'tlee')


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


def test_vault_login(docker_client):
    with VaultService.run(docker_client) as service:
        service.set_users([('james_bond', 'swordfish')])
        service.set_secrets({
            'foo': {'smee': {'lee': 23}},
            'tlee/gmoo': {'hero': 'shmero'},
        })

        client = hvac.Client(service.local_url())
        client.auth_userpass('james_bond', 'swordfish')
        assert client.is_authenticated()

        assert client.secrets.kv.read_secret('foo')['data']['data'] == {'smee': {'lee': 23}}
        assert client.secrets.kv.read_secret('tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
        assert_is_missing(client, 'tlee')


def test_vault_reuse_policy(docker_client):
    with VaultService.run(docker_client) as service:
        service.set_users([('james_bond', 'swordfish')], policy_name='agents')
        service.set_users([('bames_jond', 'swordfish')], policy_name='agents', policy=None)

        service.set_secrets({
            'foo': {'smee': {'lee': 23}},
            'tlee/gmoo': {'hero': 'shmero'},
        })

        client = hvac.Client(service.local_url())
        client.auth_userpass('bames_jond', 'swordfish')
        assert client.is_authenticated()

        assert client.secrets.kv.read_secret('foo')['data']['data'] == {'smee': {'lee': 23}}
        assert client.secrets.kv.read_secret('tlee/gmoo')['data']['data'] == {'hero': 'shmero'}
        assert_is_missing(client, 'tlee')


def test_vault_clean_secrets(docker_client):
    with VaultService.run(docker_client) as service:
        service.set_secrets({
            'a': {'v': 0},
            'a/b': {'v': 0},
            'a/b/c': {'v': 0},
            'a1/b': {'v': 0},
            'a2': {'v': 0},
        })
        with service.client() as client:
            assert client.secrets.kv.read_secret('a/b/c')['data']['data'] == {'v': 0}

        service.clear_secrets()

        with service.client() as client:
            assert_is_missing(client, 'a')
            assert_is_missing(client, 'a/b')
            assert_is_missing(client, 'a/b/c')
            assert_is_missing(client, 'a1/b')
            assert_is_missing(client, 'a2')


def test_vault_clean_some_secrets(docker_client):
    with VaultService.run(docker_client) as service:
        service.set_secrets({
            'a': {'v': 0},
            'a/b': {'v': 0},
            'a/b/c': {'v': 0},
            'a1/b': {'v': 0},
            'a2': {'v': 0},
        })
        with service.client() as client:
            assert client.secrets.kv.read_secret('a/b/c')['data']['data'] == {'v': 0}

        service.clear_secrets('a/')

        with service.client() as client:
            assert_is_missing(client, 'a/b')
            assert_is_missing(client, 'a/b/c')
            assert client.secrets.kv.read_secret('a')['data']['data'] == {'v': 0}
            assert client.secrets.kv.read_secret('a2')['data']['data'] == {'v': 0}


def test_container(docker_client, create_and_pull):
    with VaultService.run(docker_client) as service:
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv "{service.container_url()}/v1/sys/health" --fail -X "GET" -H "X-Vault-Token:guest"'
        )
        container.reload()
        assert container.attrs['State']["ExitCode"] == 0


def test_container_same_network(docker_client, create_and_pull):
    with VaultService.run(docker_client) as service:
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
