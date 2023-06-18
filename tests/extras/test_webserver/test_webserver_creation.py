import logging

from yellowbox.extras.webserver import WebServer


def test_make_server(server):
    pass


def test_make_server_with_startup_logs():
    logging.getLogger().setLevel(10)

    with WebServer("test").start():
        pass
