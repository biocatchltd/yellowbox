from typing import Callable

from httpx import Client
from pytest import fixture
from websocket import WebSocket as WSClient, create_connection as create_ws_connection

from yellowbox.extras.webserver import WebServer, http_endpoint


@fixture
def server():
    with WebServer("test").start() as server:
        yield server


@fixture
def client(server):
    return Client(base_url=server.local_url())


@fixture
def ws_client_factory(server) -> Callable[[str], WSClient]:
    def ret(url: str):
        return create_ws_connection(server.local_url("ws") + url)

    return ret


@fixture
def squib(server):
    @server.add_http_endpoint
    @http_endpoint("GET", "/bar")
    async def bar(request):
        raise ValueError("ree")

    yield bar

    # in case the squib was called, clear the pending error
    server.pending_exception = None
