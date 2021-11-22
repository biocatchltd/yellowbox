:mod:`image_build` --- Build Images Dynamically
=========================================================

.. module:: image_build
    :synopsis: Build Images Dynamically.

-------

.. function:: build_image(docker_client, image_name, remove_image = True, file = sys.stderr, spinner = True, **kwargs)

    Builds a docker image from a Dockerfile. Returns a context manager that optionally deletes the image when it exits.

    :param docker_client: A docker client to use to build the image.
    :type docker_client: :class:`~docker.client.DockerClient`
    :param str image_name: The name of the image to build, untagged.
    :param bool remove_image: Whether to remove the image after exiting the context.
    :param file: The file to write build output to. Set to ``None`` to disable printing the output, and to enable the
        spinner.
    :type file: :class:`~typing.IO`\[:class:`str`] | None
    :param bool spinner: Whether to show a spinner while building the image. Note that this will be disabled unless
        ``file`` is ``None``.
    :param \*\*kwargs: Additional keyword arguments to pass to the :meth:`~docker.api.build.BuildApiMixin.build` method.

    :returns: A context manager that yields the image name with tag, and optionally deletes the image when it exits.
    :rtype: :class:`ContextManager <contextlib.AbstractContextManager>`\[:class:`str`\]