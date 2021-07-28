from yellowbox.extras.webserver import WebServer


def test_make_server():
    with WebServer('test').start():
        pass