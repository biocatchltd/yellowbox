import json
from time import sleep

from pytest import fixture, mark, raises
from starlette.status import (
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
    WS_1000_NORMAL_CLOSURE,
    WS_1008_POLICY_VIOLATION,
)
from starlette.websockets import WebSocket
from websocket import WebSocketBadStatusException

from tests.extras.test_webserver.util import assert_ws_closed, do_some_math
from yellowbox.extras.webserver import Sender, ws_endpoint
from yellowbox.extras.webserver.ws_request_capture import RecordedWSMessage


@fixture()
def ws_calc(server):
    ep = server.add_ws_endpoint(ws_endpoint("/{a:int}/calc", do_some_math))
    return ep


def test_ws_path(server, ws_calc, ws_client_factory):
    ws_client = ws_client_factory("/12/calc")
    assert json.loads(ws_client.recv()) == 12
    ws_client.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client.recv()) == 15
    ws_client.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client.recv()) == 150
    ws_client.send('{"op":"done"}')
    assert_ws_closed(ws_client)


@mark.parametrize("close_kind", ["close", "shutdown", "abort", "drop"])
@mark.parametrize("close_on", ["send", "recv"])
def test_ws_abrupt_shutdown(server, ws_calc, ws_client_factory, close_kind, close_on):
    ws_client1 = ws_client_factory("/12/calc")
    assert json.loads(ws_client1.recv()) == 12
    if close_on == "recv":
        ws_client1.send('{"op":"add", "value": 3}')
    if close_kind == "close":
        ws_client1.close()
    elif close_kind == "shutdown":
        ws_client1.shutdown()
    elif close_kind == "abort":
        ws_client1.abort()
    else:
        pass

    ws_client2 = ws_client_factory("/14/calc")
    assert json.loads(ws_client2.recv()) == 14
    ws_client2.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client2.recv()) == 17
    ws_client2.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client2.recv()) == 170
    ws_client2.send('{"op":"done"}')
    assert_ws_closed(ws_client2)


@fixture()
def ws_squib(server):
    @server.add_ws_endpoint
    @ws_endpoint("/bar")
    async def bar(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("you remind me of the babe")
        assert await websocket.receive_text() == "what babe?"
        await websocket.send_text("the babe with the power")
        assert await websocket.receive_text() == "what power?"
        await websocket.send_text("the power of voodoo")
        assert await websocket.receive_text() == "who do?"
        await websocket.send_text("you do")
        assert await websocket.receive_text() == "do what?"
        await websocket.send_text("remind me of the babe")
        raise ValueError("dance magic")

    yield bar

    # in case the squib was called, clear the pending error
    server.pending_exception = None


def test_http_squib_ws_path(server, client, ws_client_factory, squib, ws_calc):
    assert client.get("/bar").status_code == HTTP_500_INTERNAL_SERVER_ERROR

    with raises(WebSocketBadStatusException) as exc_info:
        ws_client_factory("/12/calc")
    assert exc_info.value.status_code == HTTP_403_FORBIDDEN


def test_ws_squib_ws_path(server, ws_client_factory, ws_squib, ws_calc):
    ws_client = ws_client_factory("/bar")
    assert ws_client.recv() == "you remind me of the babe"
    ws_client.send("what babe?")
    assert ws_client.recv() == "the babe with the power"
    ws_client.send("what power?")
    assert ws_client.recv() == "the power of voodoo"
    ws_client.send("who do?")
    assert ws_client.recv() == "you do"
    ws_client.send("do what?")
    assert ws_client.recv() == "remind me of the babe"
    assert_ws_closed(ws_client, 1011)

    with raises(WebSocketBadStatusException) as exc_info:
        ws_client_factory("/12/calc")
    assert exc_info.value.status_code == HTTP_403_FORBIDDEN


@fixture()
def bridge_ep():
    @ws_endpoint("/bridge")
    async def bridge(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("what is your name?")
        if not (await websocket.receive_text()).startswith("my name is "):
            await websocket.close(WS_1008_POLICY_VIOLATION)
        else:
            await websocket.close()

    return bridge


@fixture()
def square_ep():
    @ws_endpoint("/square")
    async def square(websocket: WebSocket):
        await websocket.accept()
        i = int(await websocket.receive_text())
        await websocket.send_text(str(i * i))
        return WS_1000_NORMAL_CLOSURE

    return square


@fixture()
def cube_ep():
    @ws_endpoint("/cube")
    async def cube(websocket: WebSocket):
        await websocket.accept()
        i = int(await websocket.receive_text())
        await websocket.send_text(str(i * i * i))
        return WS_1000_NORMAL_CLOSURE

    return cube


def test_ws_no_return(server, ws_client_factory, bridge_ep):
    server.add_ws_endpoint(bridge_ep)

    ws_client = ws_client_factory("/bridge")
    assert ws_client.recv() == "what is your name?"
    ws_client.send("jimmy")
    assert_ws_closed(ws_client, 1008)

    ws_client = ws_client_factory("/bridge")
    assert ws_client.recv() == "what is your name?"
    ws_client.send("my name is jimmy")
    assert_ws_closed(ws_client, 1000)


def test_ws_calc_capture_calls(server, ws_client_factory, ws_calc):
    with ws_calc.capture_calls() as transcripts:
        ws_client = ws_client_factory("/12/calc?tee=goo")
        assert json.loads(ws_client.recv()) == 12
        ws_client.send('{"op":"add", "value": 3}')
        assert json.loads(ws_client.recv()) == 15
        ws_client.send('{"op":"mul", "value": 10}')
        assert json.loads(ws_client.recv()) == 150
        ws_client.send('{"op":"done"}')
        assert_ws_closed(ws_client, 1000)

    (transcript,) = transcripts
    assert list(transcript) == [
        RecordedWSMessage("12", Sender.Server),
        RecordedWSMessage('{"op":"add", "value": 3}', Sender.Client),
        RecordedWSMessage("15", Sender.Server),
        RecordedWSMessage('{"op":"mul", "value": 10}', Sender.Client),
        RecordedWSMessage("150", Sender.Server),
        RecordedWSMessage('{"op":"done"}', Sender.Client),
    ]
    assert transcript.accepted
    assert transcript.close == (Sender.Server, 1000)


def test_ws_parallel_capture(server, ws_calc):
    con1 = ws_calc.capture_calls()
    con2 = ws_calc.capture_calls()

    with raises(RuntimeError), con1:
        con2.__enter__()


def test_ws_multi_paths(server, ws_client_factory, cube_ep, square_ep):
    with server.patch_ws_endpoint(cube_ep):
        ws_client = ws_client_factory("/cube")
        ws_client.send("3")
        assert ws_client.recv() == "27"
        assert_ws_closed(ws_client)
        with server.patch_ws_endpoint(square_ep):
            ws_client = ws_client_factory("/cube")
            ws_client.send("3")
            assert ws_client.recv() == "27"
            assert_ws_closed(ws_client)
            ws_client = ws_client_factory("/square")
            ws_client.send("12")
            assert ws_client.recv() == "144"
            assert_ws_closed(ws_client)
        ws_client = ws_client_factory("/cube")
        ws_client.send("3")
        assert ws_client.recv() == "27"
        assert_ws_closed(ws_client)


def test_ws_readd_paths(server, ws_client_factory, square_ep):
    with raises(WebSocketBadStatusException):
        ws_client_factory("/square")
    with server.patch_ws_endpoint(square_ep):
        ws_client = ws_client_factory("/square")
        ws_client.send("12")
        assert ws_client.recv() == "144"
        assert_ws_closed(ws_client)
    with raises(WebSocketBadStatusException):
        ws_client_factory("/square")
    with server.patch_ws_endpoint(square_ep):
        ws_client = ws_client_factory("/square")
        ws_client.send("12")
        assert ws_client.recv() == "144"
        assert_ws_closed(ws_client)
    with raises(WebSocketBadStatusException):
        ws_client_factory("/square")


def test_ws_capture_client_close(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint("/bar")
    async def bar(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("do you like warhammer?")
        msg = await websocket.receive()
        assert msg["type"] == "websocket.disconnect"

    with bar.capture_calls() as transcripts:
        ws_client = ws_client_factory("/bar")
        assert ws_client.recv() == "do you like warhammer?"
        ws_client.close()

    sleep(0.1)  # give the server time to record the closing
    (transcript,) = transcripts
    assert list(transcript) == [
        RecordedWSMessage("do you like warhammer?", Sender.Server),
    ]
    assert transcript.accepted
    assert transcript.close == (Sender.Client, 1000)


def test_ws_patch(server, ws_calc, ws_client_factory):
    ws_client = ws_client_factory("/12/calc")
    assert json.loads(ws_client.recv()) == 12
    ws_client.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client.recv()) == 15
    ws_client.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client.recv()) == 150
    ws_client.send('{"op":"done"}')
    assert_ws_closed(ws_client)

    async def new_side_effect(ws: WebSocket):
        await ws.accept()
        await ws.receive()
        await ws.send_text("no")
        return WS_1000_NORMAL_CLOSURE

    with ws_calc.patch(new_side_effect):
        ws_client = ws_client_factory("/12/calc")
        ws_client.send('{"op":"add", "value": 3}')
        assert ws_client.recv() == "no"
        assert_ws_closed(ws_client)

    ws_client = ws_client_factory("/12/calc")
    assert json.loads(ws_client.recv()) == 12
    ws_client.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client.recv()) == 15
    ws_client.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client.recv()) == 150
    ws_client.send('{"op":"done"}')
    assert_ws_closed(ws_client)


def test_ws_capture_no_accept(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint("/bar")
    async def bar(websocket: WebSocket):
        await websocket.close(WS_1008_POLICY_VIOLATION)

    with bar.capture_calls() as transcripts, raises(WebSocketBadStatusException):
        ws_client_factory("/bar")

    sleep(0.1)  # give the server time to record the closing
    (transcript,) = transcripts
    assert list(transcript) == []
    assert not transcript.accepted
    assert transcript.close == (Sender.Server, 1008)


def test_ws_capture_empties(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint("/bar")
    async def bar(websocket: WebSocket):
        await websocket.accept()
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if "text" in msg:
                await websocket.send_text(msg["text"])
            else:
                await websocket.send_bytes(msg["bytes"])

    with bar.capture_calls() as transcripts:
        ws_client = ws_client_factory("/bar")
        ws_client.send_binary(b"a")
        assert ws_client.recv() == b"a"
        ws_client.send_binary(b"")
        assert ws_client.recv() == b""
        ws_client.send("")
        assert ws_client.recv() == ""
        ws_client.send("a")
        assert ws_client.recv() == "a"
        ws_client.close()

    (t,) = transcripts
    assert list(t) == [
        RecordedWSMessage(b"a", Sender.Client),
        RecordedWSMessage(b"a", Sender.Server),
        RecordedWSMessage(b"", Sender.Client),
        RecordedWSMessage(b"", Sender.Server),
        RecordedWSMessage("", Sender.Client),
        RecordedWSMessage("", Sender.Server),
        RecordedWSMessage("a", Sender.Client),
        RecordedWSMessage("a", Sender.Server),
    ]
