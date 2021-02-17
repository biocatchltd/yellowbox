import socket
import threading
import websocket
from pytest import mark, fixture, raises
from urllib.parse import urljoin

from yellowbox.extras.websocket import WebsocketService

TEST_PATH = "/test"


@fixture(scope="module")
def _global_websocket_service():
    with WebsocketService().start() as ws:
        yield ws


@fixture(scope="function")
def websocket_service(_global_websocket_service) -> WebsocketService:
    _global_websocket_service.clear()
    return _global_websocket_service


def _connect(service):
    return websocket.create_connection(urljoin(service.local_url, TEST_PATH))


def _parametrize_side_effect_response(wrapped):
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
        "expected_response,side_effect",
        [("respdata", "respdata"), (b"respdata", b"respdata"),
         ("respdata", ["respdata"]), (b"respdata", [b"respdata"]),
         (b"respdata", bytearray(b"respdata")), ("respdata", func),
         ("respdata", func2), ("respdata", gen), ("respdata", gen2),
         (b"respdata", bytefunc)])(wrapped)


@_parametrize_side_effect_response
@mark.parametrize("uri,regex", [[TEST_PATH, None], [None, "/A?test"]])
def test_websocket_route(websocket_service: WebsocketService,
                         expected_response, side_effect, uri,regex):
    websocket_service.route(uri, regex=regex)(side_effect)
    conn = _connect(websocket_service)
    assert conn.recv() == expected_response


@_parametrize_side_effect_response
@mark.parametrize("uri,regex", [[TEST_PATH, None], [None, "/A?test"]])
def test_websocket_add(websocket_service: WebsocketService,
                       expected_response, side_effect, uri, regex):
    websocket_service.add(side_effect, uri, regex=regex)
    conn = _connect(websocket_service)
    assert conn.recv() == expected_response


@_parametrize_side_effect_response
@mark.parametrize("uri,regex", [[TEST_PATH, None], [None, "/A?test"]])
def test_websocket_set(websocket_service: WebsocketService,
                       expected_response, side_effect, uri, regex):
    websocket_service.set(side_effect, uri, regex=regex)
    conn = _connect(websocket_service)
    assert conn.recv() == expected_response


@_parametrize_side_effect_response
@mark.parametrize("uri,regex", [[TEST_PATH, None], [None, "/A?test"]])
def test_websocket_patch(websocket_service: WebsocketService,
                         expected_response, side_effect, uri, regex):
    patch = websocket_service.patch(side_effect, uri, regex=regex)

    with patch:
        conn = _connect(websocket_service)
        assert conn.recv() == expected_response


def test_websocket_double_add(websocket_service: WebsocketService):
    websocket_service.add("test", "test")
    with raises(RuntimeError):
        websocket_service.add("test", "test")


def test_websocket_double_route(websocket_service: WebsocketService):
    websocket_service.route("test")("test")
    with raises(RuntimeError):
        websocket_service.route("test")("test")


def test_websocket_double_set(websocket_service: WebsocketService):
    websocket_service.set("test", "test")
    websocket_service.set("test", "test")  # No error


def test_websocket_double_patch(websocket_service: WebsocketService):
    with websocket_service.patch("test", "test"), raises(RuntimeError), \
            websocket_service.patch("test", "test"):
        pass


def test_websocket_remove(websocket_service: WebsocketService):
    websocket_service.add("test", "test")
    websocket_service.remove("test")
    with raises(KeyError):
        websocket_service.remove("test")


def test_websocket_remove_regex(websocket_service: WebsocketService):
    websocket_service.add("test", regex="test")
    websocket_service.remove(regex="test")
    with raises(KeyError):
        websocket_service.remove(regex="test")


def test_websocket_clear(websocket_service: WebsocketService):
    websocket_service.add("test", "test")
    websocket_service.clear()
    # Make sure it was cleared, no error.
    websocket_service.add("test", "test")


def test_websocket_generator_recv(websocket_service: WebsocketService):
    event = threading.Event()
    data = []

    def gen(ws):
        data.append((yield))
        data.append((yield))
        event.set()
    websocket_service.add(gen, TEST_PATH)
    conn = _connect(websocket_service)
    conn.send("testy")
    conn.send("bin")
    event.wait()
    assert data == ["testy", "bin"]
    conn.close()


def test_websocket_stop():
    # prevent stoppping session websocket.
    websocket_service = WebsocketService()
    websocket_service.start()
    done = False

    def stuck(ws):
        nonlocal done
        try:
            while True:
                yield  # Should be able to close while a generator is stuck.
        finally:
            done = True
    websocket_service.add(stuck, TEST_PATH)
    conn = _connect(websocket_service)
    conn.send("test")
    websocket_service.stop()
    assert done

    # Make sure we're actually closed.
    with raises((ConnectionRefusedError, socket.timeout)):
        websocket.create_connection(
            urljoin(websocket_service.local_url, TEST_PATH), timeout=0.2)


def test_websocket_nonexisting_route(websocket_service: WebsocketService):
    conn = _connect(websocket_service)
    conn.send("asd")

    # Should be auto-closed.
    with raises(ConnectionAbortedError):
        conn.send("asd")
