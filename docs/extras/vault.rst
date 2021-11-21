:mod:`extras.vault` --- Hashicorp Vault Secrets Management
===============================================================

.. module:: extras.vault
    :synopsis: Hashicorp Vault Secrets Management

-------

A :class:`~service.YellowService` for running a Hashicorp Vault service. Runs the official Vault docker image.

.. note::

    Requires the ``vault`` extra. For more information, see our :ref:`installation guide <installation>`.

.. class:: VaultService(docker_client, image="redis:latest", root_token="guest",\
                        **kwargs)

    A service to run the redis database. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin`.

    :param docker_client: The docker client to used to pull and create the Vault container.
    :type docker_client: :class:`docker.DockerClient<docker.client.DockerClient>`

    :param str image: The image name to create a container of.

    :param str root_token: the root access token string for the new vault container.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:
    
    .. method:: client_port() -> int

        Returns the port to be used when connecting to the vault server from the docker host.

    .. method:: local_url() -> str

        Returns the HTTP URL to be used when connecting to the vault server from the local host.

    .. method:: container_url() -> str

        Returns the HTTP URL to be used when connecting to the vault server from a container through the docker host.

    .. method:: sibling_container_url(container_alias) -> str

        Returns the HTTP URL to be used when connecting to the vault server from a container through a shared network.

        :param str container_alias: The alias of the vault container within the network.

    .. method:: client(**kwargs) -> typing.ContextManager[hvac.Client]

        Returns a context manager that creates a :class:`<hvac Client> hvac.v1.Client` with root privilege, and closes
        the client when exited.

        :param \*\*kwargs: Additional keyword arguments passed to :class:`~hvac.v1.Client`.

    .. method:: set_users(userpass, policy_name='dev', policy=...) -> typing.ContextManager[hvac.Client]

        creates or updates a collection of users with a specific policy.

        :param userpass: An iterable of username-password tuples.
        :type userpass: :class:`~collections.abc.Iterable`\[:class:`tuple`\[:class:`str`, :class:`str`]]

        :param str policy_name: The name of the policy to be applied to the users.

        :param dict | None policy: If not ``None``, creates or updates a policy with the name *policy_name* and access
            in accordance with *policy* as a `JSON style policy syntax object
            <https://www.vaultproject.io/docs/concepts/policies#policy-syntax>`_. Default is a policy with read-only
            access to all secrets.

    .. method:: set_secrets(secrets):

        creates or updates a secrets in the service.

        :param secrets: A mapping of paths to secret value objects.
        :type secrets: :class:`~collections.abc.Mapping`\[:class:`str`, :class:`~collections.abc.Mapping`
            \[:class:`str`, ...]]

    .. method:: clear_secrets(root_path='/'):

        Recursively removes all secrets and subdirectories under the given root path.

        :param str root_path: The root path to delete all secrets under. Must end with a slash.

        .. note::

            This method will not delete the root path itself if a secret is assigned to it.