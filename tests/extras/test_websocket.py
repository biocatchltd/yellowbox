import websocket
from pytest import mark, fixture
from urllib.parse import urljoin

from yellowbox.extras.websocket import WebsocketService

TEST_PATH = "/test"


@fixture(scope="module")
def global_websocket_service():
    with WebsocketService().start() as ws:
        yield ws


@fixture(scope="function")
def websocket_service(global_websocket_service) -> WebsocketService:
    global_websocket_service.clear()
    return global_websocket_service


def _connect(service):
    return websocket.create_connection(urljoin(service.local_url, TEST_PATH))


def _parametrize_side_effect(wrapped):
    def func(websocket):
        return "respdata"

    def func2(websocket):
        websocket.send_message("respdata")

    def gen(websocket):
        yield "respdata"

    def gen2(websocket):
        websocket.send_message("respdata")
        return
        yield  # noqa

    def bytefunc(websocket):
        return b"respdata"

    return mark.parametrize(
        "side_effect",
        [("respdata", "respdata"), (b"respdata", b"respdata"),
         (b"respdata", bytearray(b"respdata")), ("respdata", func),
         ("respdata", func2), ("respdata", gen), ("respdata", gen2),
         (b"respdata", bytefunc)])(wrapped)


@_parametrize_side_effect
def test_websocket_route(websocket_service: WebsocketService, side_effect):
    expected_response, side_effect = side_effect
    websocket_service.route(TEST_PATH)(side_effect)
    conn = _connect(websocket_service)
    assert conn.recv() == expected_response
