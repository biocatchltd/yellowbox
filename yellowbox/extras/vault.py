from contextlib import contextmanager
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Tuple

import hvac
from docker import DockerClient
from hvac.exceptions import VaultError
from requests.exceptions import ConnectionError

from yellowbox.containers import create_and_pull, get_ports
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, RunMixin, SingleContainerService
from yellowbox.utils import docker_host_name

__all__ = ['VAULT_DEFAULT_PORT', 'DEV_POLICY', 'VaultService']

VAULT_DEFAULT_PORT = 8200

DEV_POLICY = {
    "path": {
        "secret/*": {
            "capabilities": ["read"]
        },
    }
}


class VaultService(SingleContainerService, RunMixin, AsyncRunMixin):
    """
    A yellow service for Hashicorp Vault, with hvac as a client. The vault container is in dev mode AND SHOULD ONLY BE
    USED FOR DEVELOPMENT.
    """

    def __init__(self, docker_client: DockerClient, image='vault:latest', root_token: str = 'guest', **kwargs):
        """
        Args:
            docker_client: the client to use
            image: the image name and tag of the vault image
            root_token: the token string for the new vault container, with root access
            **kwargs: forwarded to SingleContainerService
        """
        container = create_and_pull(docker_client, image, publish_all_ports=True, detach=True, environment={
            'VAULT_DEV_ROOT_TOKEN_ID': root_token,
        })
        self.started = False
        self.root_token = root_token
        super().__init__(container, **kwargs)

    def client_port(self):
        return get_ports(self.container)[VAULT_DEFAULT_PORT]

    def local_url(self):
        return f'http://127.0.0.1:{self.client_port()}'

    def container_url(self):
        return f'http://{docker_host_name}:{self.client_port()}'

    def sibling_container_url(self, container_alias):
        return f'http://{container_alias}:{VAULT_DEFAULT_PORT}'

    @contextmanager
    def client(self, **kwargs) -> Iterator[hvac.Client]:  # type: ignore
        """
        Get a context manager that creates and closes a root-access hvac client
        Args:
            **kwargs: forwarded to hvac.Client constructor
        """
        client = hvac.Client(url=self.local_url(), token=self.root_token, **kwargs)
        try:
            yield client
        finally:
            client.adapter.close()

    def _check_health(self):
        with self.client() as client:
            client.lookup_token()

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()

        retry_spec = retry_spec or RetrySpec(attempts=10)

        retry_spec.retry(self._check_health, (VaultError, ConnectionError))
        with self.client() as client:
            client.sys.enable_auth_method('userpass')
        self.started = True
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None) -> None:
        super().start(retry_spec)

        retry_spec = retry_spec or RetrySpec(attempts=10)

        await retry_spec.aretry(self._check_health, (VaultError, ConnectionError))
        with self.client() as client:
            client.sys.enable_auth_method('userpass')
        self.started = True

    def set_users(self, userpass: Iterable[Tuple[str, str]], policy_name='dev', policy: Optional[Mapping] = DEV_POLICY):
        """
        Create and set users with policies
        Args:
            userpass: an iterable of users and passwords to create
            policy_name: the name of the policy to assign to the new users
            policy: if assigned, will create or override `profile_name` with the policy dict provided. Default is a
             policy that can read all secrets
        """
        with self.client() as client:
            if policy:
                client.sys.create_or_update_policy(policy_name, policy)
            for username, password in userpass:
                client.auth.userpass.create_or_update_user(username, password, policies=[policy_name])

    def set_secrets(self, secrets: Mapping[str, Mapping[str, Any]]):
        """
        Create and set secrets in the vault
        Args:
            secrets: a dict of secrets, mapping paths to json objects to store
        """
        with self.client() as client:
            for k, v in secrets.items():
                client.secrets.kv.create_or_update_secret(k, v)

    def clear_secrets(self, root_path='/'):
        """
        permanently remove all secrets and subdirectories from a directory in vault
        Args:
            root_path: the root path to delete, default removes all secrets in the vault
        Notes:
            if a secret is assigned to the directory itself, the secret will not be deleted
        """
        if not root_path.endswith('/'):
            raise ValueError('path must end with slash "/"')
        client: hvac.Client
        with self.client() as client:
            def clear_recursive(path):
                secret_names: List[str] = client.secrets.kv.list_secrets(path)['data']['keys']
                for name in secret_names:
                    if name.endswith('/'):
                        # is a directory
                        clear_recursive(path + name)
                    else:
                        # is a secret
                        client.secrets.kv.delete_metadata_and_all_versions(path + name)

            clear_recursive(root_path)
