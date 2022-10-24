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