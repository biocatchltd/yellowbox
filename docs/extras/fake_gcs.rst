:mod:`extras.fake_gcs` --- Google Cloud Storage Emulation
=============================================================

.. module:: extras.fake_gcs
    :synopsis: Emulate Google Cloud Storage.

-------

A :class:`~service.YellowService` emulating Google Cloud Storage. Runs the
docker image of `fake-gcs-server <https://github.com/fsouza/fake-gcs-server>`_,
fsouza's unofficial emulator. You may use any client such as
`google-cloud-storage <https://pypi.org/project/google-cloud-storage/>`_ to connect
to the service.

.. note::

    Requires the ``gcs`` extra. For more information, see our :ref:`installation guide <installation>`.

.. class:: FakeGoogleCloudStorage(docker_client: docker.client.DockerClient,\
    image : str="fsouza/fake-gcs-server:latest", scheme: str = "https", command: str = "", **kwargs)

    A service that runs an fake GCS server. Inherits from :class:`~subclasses.SingleContainerService`. Usable with
    :class:`~subclasses.RunMixin` and :class:`~subclasses.AsyncRunMixin`.

    :param docker_client: The docker client to used to pull and create the Azurite container.

    :param image: The image name to create a container of.

    :param scheme: the scheme of the face service to serve

    :param command: additional suffix to the service startup command (:code:`docker run --rm fsouza/fake-gcs-server:latest
       -help` for a full list of commands)

    :param \*\*kwargs: Additional keyword arguments passed to :class:`~subclasses.SingleContainerService`.

    Has the following additional methods:

    .. method:: client_port()->int

        Returns the port to be used when connecting to GCS from the docker host.

    .. method:: local_url(scheme: Optional[str] = ...)->str

        Returns a url to connect from host to container.

        :param scheme: If used, will format the scheme of the url with the one provided, default is to use the scheme
           given to the service during construction. If `None`, the url will not include a scheme.

        .. note::
            To connect from a different container, see :meth:`container_url` or :meth:`host_url`.

    .. method:: container_url(alias: str, hostname: Optional[str] = ...)->str

        Returns a url to connect from containers in a common network.

        :param hostname: The alias of the fake GCS container within the network.
        :param scheme: If used, will format the scheme of the url with the one provided, default is to use the scheme
           given to the service during construction. If `None`, the url will not include a scheme.

    .. method:: host_url(scheme: Optional[str] = ...)->str

        Returns a url to connect from containers across the docker host.

        :param scheme: If used, will format the scheme of the url with the one provided, default is to use the scheme
           given to the service during construction. If `None`, the url will not include a scheme.

    .. method:: patch_gcloud_aio()->contextlib.AbstractContextManager

        Patches the global variables in the `gcloud-aio-storage\
        <https://github.com/talkiq/gcloud-aio/blob/master/storage/README.rst>`_ module, making new storage clients
        target `self` as an emulator. Returns a context manager that changes the global variables and restores them on
        exit.

        :raises ImportError: if gcloud-aio-storage is not installed

        .. code-block::
            :caption: Example

            cgs: FakeGoogleCloudStorage
            with cgs.patch_gcloud_aio():
                async with ClientSession(connector=TCPConnector(ssl=False)) as session:
                    storage = Storage(session=session)  # this storage will connect to gcs

        .. warning::

            This feature is temperamental as it effectively changes consts in an external module. No storage client
            created inside the context should exist outside of it and vice-versa.

    .. method:: create_bucket(bucket_name: str) -> dict[str, typing.Any]

        Creates a new bucket in the emulator. Returns the parsed response from the container (supposed to follow the
        `google api <https://cloud.google.com/storage/docs/json_api/v1/buckets/insert#response>`_)

        :param bucket_name: The name of the bucket to create

    .. method:: clear_bucket(bucket_name: str, prefix: str | None = None) -> collections.abc.Iterable[str]

        Removes all objects in a bucket. Returns an iterable of the names of all objects deleted.

        :param bucket_name: The name of the bucket to clear.
        :param prefix: If specified, will only delete object with the specified prefix.

    .. method:: delete_bucket(bucket_name: str, force: bool = False, missing_ok: bool = False)

        Deletes a bucket in the emulator.

        :param bucket_name: The name of the bucket to delete
        :param force: If set to `True`, will also delete all objects in the bucket beforehand. Deleting a non-empty
            bucket without `force=True` will raise an exception.
        :param missing_ok: If set to `True`, will not raise an exception if the bucket does not exist.