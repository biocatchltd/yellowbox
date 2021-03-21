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

    If you wish to use this package, please install Yellowbox with the ``azure``
    extra. For more information, see our
    :ref:`installation guide <installation>`.

.. class:: BlobStorageService(docker_client,\
    image="mcr.microsoft.com/azure-storage/azurite:latest", **kwargs)

    A :class:`~subclasses.SingleContainerService` used to run Azurite.

    *docker_client* is a ``docker.py`` client used to pull Azurite and create
    the container during instance construction.

    *image* is the Azurite image to use. Defaults to the latest official build.

    Further `kwargs` are passed to the parent classes' constructor.

    Inherits from :class:`~subclasses.SingleContainerService` and
    :class:`subclasses.RunMixin`.

    Has the following additional methods:

    .. method:: client_port()

        Returns the port to be used when connecting to Azurite.

    .. method:: connection_string()

        Returns a connection string to connect from host to container.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        If you wish to connect from a different container, see
        :meth:`container_connection_string`.

    .. method:: container_connection_string()

        Returns a connection string to connect across containers in the same network.

        The connection string is formatted according to Microsoft's
        `specification <https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string#connect-to-the-emulator-account-using-the-shortcut>`_.

        If you wish to connect from the local host, see :meth:`connection_string`.

    .. method:: endpoint_url()

        Returns an endpoint URL to connect from docker host.

    .. method:: container_endpoint_url()

        Returns an endpoint URL to connect across containers.

    .. method:: account_credentials()

        Returns a credential dict to connect to the service.

        The dict consists of an ``account_name`` and an ``account_key``.
