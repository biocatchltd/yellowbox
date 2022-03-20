Pytest Integration
======================

Yellowbox comes pre-equipped with a pytest plugin that provides a fixture for easier testing.

docker_client
---------------

This session-scoped fixture provides a docker client, as constructed by :func:`clients.open_docker_client`.