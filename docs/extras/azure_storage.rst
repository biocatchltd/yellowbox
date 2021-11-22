:mod:`extras.azure_storage` --- Azure Cloud Storage Emulation
=============================================================

.. module:: extras.azure_storage
    :synopsis: Emulate Azure Cloud Storage.

-------

A :class:`~service.YellowService` emulating Azure Cloud Storage. Runs the
docker image of `Azurite\
<https://docs.microsoft.com/en-us/azure/storage/common/storage-use-azurite>`_,
Microsoft's official emulator. You may use any client such as
`azure-storage-blob <https://pypi.org/project/azure-storage-blob/>`_ to connect
to the service.

.. note::

    Requires the ``azure`` extra. For more information, see our :ref:`installation guide <installation>`.

.. note::

    Currently, the service only supports the default
    `Azure Storage account <https://github.com/Azure/Azurite/blob/main/README.md#user-content-default-storage-account>`_.

.. class:: BlobStorageService(docker_client,\
    image="mcr.microsoft.com/azure-storage/azurite:latest", **kwargs)

    A service that runs an Azurite server. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin`.

    :param docker_client: The docker client to used to pull and create the Azurite container.
    :type docker_client: :class:`~docker.client.DockerClient`

    :param str image: The image name to create a container of.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: client_port()->int

        Returns the port to be used when connecting to Azurite.

    .. method:: connection_string()->str

        Returns a connection string to connect from host to container.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        .. note::
            To connect from a different container, see :meth:`container_connection_string`.

    .. method:: container_connection_string()->str

        Returns a connection string to connect from containers in a common network with the Azurite service.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        .. note::
            To connect from the local host, see :meth:`connection_string`.

    .. method:: endpoint_url() -> str

        Returns an endpoint HTTP URL to connect from docker host.

    .. method:: container_endpoint_url() -> str

        Returns an endpoint HTTP URL to connect to from containers in a common network with the Azurite service.

    .. method:: account_credentials()

        Returns a credential dict to connect to the service. The dict consists of 2 keys:
        ``"account_name"`` and ``"account_key"``, and can be used as ``credentials`` for the `azure-storage-blob
        BlobServiceClient constructor <https://docs.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobserviceclient?view=azure-python#constructor>`_.

    .. attribute:: account_name
        :type: str

        The account name, as registered in Azurite.

        .. note::

            Since ``BlobStorageService`` currently only supports the default azurite account, this attribute should not
            be changed.

    .. attribute:: account_key
        :type: str

        The account password, as registered in Azurite.

        .. note::

            Since ``BlobStorageService`` currently only supports the default azurite account, this attribute should not
            be changed.
