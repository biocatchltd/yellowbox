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

.. class:: AzuriteService(docker_client: docker.client.DockerClient,\
    image : str="mcr.microsoft.com/azure-storage/azurite:latest", *, \
    container_create_kwargs: dict[str, typing.Any] | None = None, **kwargs)

    A service that runs an Azurite server. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin` and :class:`~subclasses.AsyncRunMixin`.

    :param docker_client: The docker client to used to pull and create the Azurite container.

    :param image: The image name to create a container of.

    :param container_create_kwargs: Additional keyword arguments passed to :meth:`docker.models.containers.ContainerCollection.create`.

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: client_port()->int

        Returns the port to be used when connecting to Azurite from the docker host.

    .. method:: connection_string()->str

        Returns a connection string to connect from host to container.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        .. note::
            To connect from a different container over a network, see :meth:`container_connection_string`.

        .. note::
            To connect from a container through the docker host, see :meth:`host_connection_string`

    .. method:: container_connection_string()->str

        Returns a connection string to connect from containers in a common network with the Azurite service.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        .. note::
            To connect from the local host, see :meth:`connection_string`.

        .. note::
            To connect from a container through the docker host, see :meth:`host_connection_string`

    .. method:: host_connection_string()->str

        Returns a connection string to connect from containers to the Azurite service, through the docker host.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        .. note::
            To connect from the local host, see :meth:`connection_string`.

        .. note::
            To connect containers over a network, see :meth:`container_connection_string`.

    .. method:: endpoint_url() -> str

        Returns an endpoint HTTP URL to connect from docker host.

    .. method:: container_endpoint_url() -> str

        Returns an endpoint HTTP URL to connect to from containers in a common network with the Azurite service.

    .. method:: host_endpoint_url() -> str

        Returns an endpoint HTTP URL to connect to from containers to the Azurite service, through the docker host.

    .. method:: account_credentials()->dict

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

.. class:: BlobStorageService(...)

    A legacy alias of :class:`AzuriteService`.