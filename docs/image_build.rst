:mod:`image_build` --- Build Images Dynamically
=========================================================

.. module:: image_build
    :synopsis: Build Images Dynamically.

-------

.. function:: build_image(docker_client: docker.client.DockerClient, image_name: str, remove_image: bool = True,\
        file: typing.IO[str] = sys.stderr, spinner: bool = True, **kwargs)->contextlib.AbstractContextManager[str]

    Builds a docker image from a Dockerfile. Returns a context manager that optionally deletes the image when it exits.

    :param docker_client: A docker client to use to build the image.
    :param image_name: The name of the image to build.  If no tag is provided, the tag "test" will be added to the
        final image.
    :param remove_image: Whether to remove the image after exiting the context.
    :param file: The file to write build output to. Set to ``None`` to disable printing the output, and to enable the
        spinner.
    :param spinner: Whether to show a spinner while building the image. Note that this will be disabled unless
        ``file`` is ``None``.
    :param \*\*kwargs: Additional keyword arguments to pass to the :meth:`~docker.api.build.BuildApiMixin.build` method.

    :returns: A context manager that yields the image name with tag, and optionally deletes the image when it exits.