import json
import re
from io import StringIO
from time import sleep
from typing import Callable

from httpx import Client, HTTPError, get
from pytest import fixture, raises
from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.status import (
    HTTP_200_OK, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR, WS_1000_NORMAL_CLOSURE,
    WS_1008_POLICY_VIOLATION
)
from starlette.websockets import WebSocket
from websocket import WebSocket as WSClient, WebSocketBadStatusException, create_connection as create_ws_connection

from yellowbox.extras.webserver import MockHTTPEndpoint, MockWSEndpoint, WebServer, http_endpoint, ws_endpoint
from yellowbox.extras.webserver.class_endpoint import class_http_endpoint, class_ws_endpoint
from yellowbox.extras.webserver.util import iter_side_effects, verbose_http_side_effect
from yellowbox.extras.webserver.webserver import HandlerError
from yellowbox.extras.webserver.ws_request_capture import RecordedWSMessage, Sender


def assert_ws_closed(ws_client: WSClient, code: int = 1000):
    resp_opcode, msg = ws_client.recv_data()
    assert resp_opcode == 8
    assert msg == code.to_bytes(2, 'big')


@fixture
def server():
    with WebServer('test').start() as server:
        yield server


@fixture
def client(server):
    return Client(base_url=server.local_url())


@fixture
def ws_client_factory(server) -> Callable[[str], WSClient]:
    def ret(url: str):
        return create_ws_connection(server.local_url('ws') + url)

    return ret


def test_make_server(server):
    pass


def test_capture(server, client):
    endpoint = server.add_http_endpoint('GET', '/api/foo', side_effect=PlainTextResponse('hewwo'))
    with endpoint.capture_calls() as calls0:
        assert calls0 == []

        with endpoint.capture_calls() as calls1:
            assert calls1 == []
            resp = client.get('/api/foo?a=15&a=17')
            assert resp.status_code == 200
            assert resp.text == 'hewwo'

        c1, = calls1
        assert c1.method == 'GET'
        assert c1.path == "/api/foo"
        assert c1.path_params == {}
        assert c1.query_params == {'a': ['15', '17']}

        resp = client.get('/api/foo')
        assert resp.status_code == 200
        assert resp.text == 'hewwo'
    c0_0, c0_1 = calls0
    assert c0_0 == c1


def test_mock_callable(server, client):
    @server.add_http_endpoint
    @http_endpoint('POST', '/{a:int}/foo')
    async def get_foo(request: Request):
        a = request.path_params['a']
        b = await request.json()
        return JSONResponse(a * b)

    resp = client.post('/12/foo', json=15)
    resp.raise_for_status()
    assert resp.json() == 15 * 12

    with get_foo.patch(JSONResponse(["a", "b"])):
        resp = client.post('/12/foo', json=15)
        resp.raise_for_status()
        assert resp.json() == ["a", "b"]

    resp = client.post('/12/foo', json=10)
    resp.raise_for_status()
    assert resp.json() == 10 * 12


def test_remove_path():
    with WebServer('test').start() as server:
        client = Client(base_url=server.local_url())

        @http_endpoint('POST', '/{a:int}/foo')
        async def get_foo(request):
            a = request.path_params['a']
            b = await request.json()
            return JSONResponse(a * b)

        assert client.post('/12/foo', json=15).status_code == HTTP_404_NOT_FOUND
        assert client.post('/12/bar', json=15).status_code == HTTP_404_NOT_FOUND

        with server.patch_http_endpoint(get_foo):
            resp = client.post('/12/foo', json=15)
            resp.raise_for_status()
            assert resp.json() == 15 * 12

        assert client.post('/12/foo', json=15).status_code == HTTP_404_NOT_FOUND
        assert client.post('/12/bar', json=15).status_code == HTTP_404_NOT_FOUND
    with raises(HTTPError):
        client.post('/12/foo', json=15)


def test_multi_paths(server, client):
    with server.patch_http_endpoint('GET', '/foo', PlainTextResponse('hi')):
        resp = client.get('/foo')
        resp.raise_for_status()
        assert resp.text == 'hi'
        with server.patch_http_endpoint('GET', '/bar', PlainTextResponse('ho')):
            resp = client.get('/foo')
            resp.raise_for_status()
            assert resp.text == 'hi'
            resp = client.get('/bar')
            resp.raise_for_status()
            assert resp.text == 'ho'
        resp = client.get('/foo')
        resp.raise_for_status()
        assert resp.text == 'hi'
        assert client.get('/bar').status_code == HTTP_404_NOT_FOUND


def test_readd_endpoint(server, client):
    ep = http_endpoint('GET', '/foo', PlainTextResponse('hi'))
    assert client.get('/foo').status_code == HTTP_404_NOT_FOUND
    with server.patch_http_endpoint(ep):
        resp = client.get('/foo')
        resp.raise_for_status()
        assert resp.text == 'hi'
    assert client.get('/foo').status_code == HTTP_404_NOT_FOUND
    with server.patch_http_endpoint(ep):
        resp = client.get('/foo')
        resp.raise_for_status()
        assert resp.text == 'hi'
    assert client.get('/foo').status_code == HTTP_404_NOT_FOUND


@fixture
def squib(server):
    @server.add_http_endpoint
    @http_endpoint('GET', '/bar')
    async def bar(request):
        raise ValueError('ree')

    yield bar

    # in case the squib was called, clear the pending error
    server._pending_exception = None


def test_handler_error(server, client, squib):
    assert client.get('/bar').status_code == HTTP_500_INTERNAL_SERVER_ERROR
    with raises(HandlerError) as exc_info:
        server.is_alive()
    cause = exc_info.value.__cause__
    assert isinstance(cause, ValueError)
    assert cause.args == ('ree',)


def test_handler_error_stuck(server, client, squib):
    server.add_http_endpoint('GET', '/foo', PlainTextResponse('voodoo'))
    assert client.get('/foo').status_code == HTTP_200_OK
    assert client.get('/bar').status_code == HTTP_500_INTERNAL_SERVER_ERROR
    resp = client.get('/foo')
    assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert "ValueError('ree')" in resp.text
    with raises(HandlerError):
        server.is_alive()


def test_methods(server, client):
    server.add_http_endpoint(('POST', 'GET'), '/foo', PlainTextResponse('voodoo'))
    resp = client.post('/foo')
    resp.raise_for_status()
    assert resp.text == 'voodoo'
    resp = client.get('/foo')
    resp.raise_for_status()
    assert resp.text == 'voodoo'

    assert client.put('/foo').status_code == 405
    assert client.head('/foo').status_code == 405


def test_methods_with_head(server, client):
    server.add_http_endpoint(('POST', 'GET'), '/foo', PlainTextResponse('voodoo'), forbid_implicit_head_verb=False)
    resp = client.post('/foo')
    resp.raise_for_status()
    assert resp.text == 'voodoo'
    resp = client.get('/foo')
    resp.raise_for_status()
    assert resp.text == 'voodoo'
    resp = client.head('/foo')
    resp.raise_for_status()
    assert not resp.content

    assert client.put('/foo').status_code == 405


def test_no_auto_read(server, client):
    ep = server.add_http_endpoint('GET', '/foo', PlainTextResponse('voodoo'), auto_read_body=False)
    resp = client.get('/foo')
    resp.raise_for_status()
    assert resp.text == 'voodoo'

    with raises(RuntimeError):
        with ep.capture_calls():
            ...


def test_parallel_capture(server):
    ep = server.add_http_endpoint('GET', '/foo', PlainTextResponse('voodoo'))
    con1 = ep.capture_calls()
    con2 = ep.capture_calls()

    with raises(RuntimeError):
        with con1:
            con2.__enter__()


async def do_some_math(ws: WebSocket):
    await ws.accept()
    query_args = QueryParams(ws.scope["query_string"])
    if 'mod' in query_args:
        mod = int(query_args['mod'])
    else:
        mod = None

    v = ws.scope['path_params']['a']
    while True:
        if mod:
            v %= mod
        await ws.send_json(v)
        operation = await ws.receive_json()
        action = operation.get('op')
        if not action:
            return WS_1008_POLICY_VIOLATION
        if action == 'done':
            return WS_1000_NORMAL_CLOSURE
        operand = operation.get('value')
        if operand is None:
            return WS_1008_POLICY_VIOLATION
        if action == 'add':
            v += operand
            continue
        if action == 'mul':
            v *= operand
            continue


@fixture
def ws_calc(server):
    ep = server.add_ws_endpoint(ws_endpoint('/{a:int}/calc', do_some_math))
    return ep


def test_ws_path(server, ws_calc, ws_client_factory):
    ws_client = ws_client_factory('/12/calc')
    assert json.loads(ws_client.recv()) == 12
    ws_client.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client.recv()) == 15
    ws_client.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client.recv()) == 150
    ws_client.send('{"op":"done"}')
    assert_ws_closed(ws_client)


@fixture
def ws_squib(server):
    @server.add_ws_endpoint
    @ws_endpoint('/bar')
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
        raise ValueError('dance magic')

    yield bar

    # in case the squib was called, clear the pending error
    server._pending_exception = None


def test_http_squib_ws_path(server, client, ws_client_factory, squib, ws_calc):
    assert client.get('/bar').status_code == HTTP_500_INTERNAL_SERVER_ERROR

    with raises(WebSocketBadStatusException) as exc_info:
        ws_client_factory('/12/calc')
    assert exc_info.value.status_code == HTTP_403_FORBIDDEN


def test_ws_squib_ws_path(server, ws_client_factory, ws_squib, ws_calc):
    ws_client = ws_client_factory('/bar')
    assert ws_client.recv() == 'you remind me of the babe'
    ws_client.send("what babe?")
    assert ws_client.recv() == 'the babe with the power'
    ws_client.send("what power?")
    assert ws_client.recv() == 'the power of voodoo'
    ws_client.send("who do?")
    assert ws_client.recv() == 'you do'
    ws_client.send("do what?")
    assert ws_client.recv() == 'remind me of the babe'
    assert_ws_closed(ws_client, 1011)

    with raises(WebSocketBadStatusException) as exc_info:
        ws_client_factory('/12/calc')
    assert exc_info.value.status_code == HTTP_403_FORBIDDEN


@fixture
def bridge_ep():
    @ws_endpoint('/bridge')
    async def bridge(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text('what is your name?')
        if not (await websocket.receive_text()).startswith('my name is '):
            await websocket.close(WS_1008_POLICY_VIOLATION)
        else:
            await websocket.close()

    return bridge


@fixture
def square_ep():
    @ws_endpoint('/square')
    async def square(websocket: WebSocket):
        await websocket.accept()
        i = int(await websocket.receive_text())
        await websocket.send_text(str(i * i))
        return WS_1000_NORMAL_CLOSURE

    return square


@fixture
def cube_ep():
    @ws_endpoint('/cube')
    async def cube(websocket: WebSocket):
        await websocket.accept()
        i = int(await websocket.receive_text())
        await websocket.send_text(str(i * i * i))
        return WS_1000_NORMAL_CLOSURE

    return cube


def test_ws_no_return(server, ws_client_factory, bridge_ep):
    server.add_ws_endpoint(bridge_ep)

    ws_client = ws_client_factory('/bridge')
    assert ws_client.recv() == 'what is your name?'
    ws_client.send('jimmy')
    assert_ws_closed(ws_client, 1008)

    ws_client = ws_client_factory('/bridge')
    assert ws_client.recv() == 'what is your name?'
    ws_client.send('my name is jimmy')
    assert_ws_closed(ws_client, 1000)


def test_ws_calc_capture_calls(server, ws_client_factory, ws_calc):
    with ws_calc.capture_calls() as transcripts:
        ws_client = ws_client_factory('/12/calc?tee=goo')
        assert json.loads(ws_client.recv()) == 12
        ws_client.send('{"op":"add", "value": 3}')
        assert json.loads(ws_client.recv()) == 15
        ws_client.send('{"op":"mul", "value": 10}')
        assert json.loads(ws_client.recv()) == 150
        ws_client.send('{"op":"done"}')
        assert_ws_closed(ws_client, 1000)

    transcript, = transcripts
    assert list(transcript) == [
        RecordedWSMessage('12', Sender.Server),
        RecordedWSMessage('{"op":"add", "value": 3}', Sender.Client),
        RecordedWSMessage('15', Sender.Server),
        RecordedWSMessage('{"op":"mul", "value": 10}', Sender.Client),
        RecordedWSMessage('150', Sender.Server),
        RecordedWSMessage('{"op":"done"}', Sender.Client),
    ]
    assert transcript.accepted
    assert transcript.close == (Sender.Server, 1000)


def test_ws_parallel_capture(server, ws_calc):
    con1 = ws_calc.capture_calls()
    con2 = ws_calc.capture_calls()

    with raises(RuntimeError):
        with con1:
            con2.__enter__()


def test_ws_multi_paths(server, ws_client_factory, cube_ep, square_ep):
    with server.patch_ws_endpoint(cube_ep):
        ws_client = ws_client_factory('/cube')
        ws_client.send('3')
        assert ws_client.recv() == '27'
        assert_ws_closed(ws_client)
        with server.patch_ws_endpoint(square_ep):
            ws_client = ws_client_factory('/cube')
            ws_client.send('3')
            assert ws_client.recv() == '27'
            assert_ws_closed(ws_client)
            ws_client = ws_client_factory('/square')
            ws_client.send('12')
            assert ws_client.recv() == '144'
            assert_ws_closed(ws_client)
        ws_client = ws_client_factory('/cube')
        ws_client.send('3')
        assert ws_client.recv() == '27'
        assert_ws_closed(ws_client)


def test_ws_readd_paths(server, ws_client_factory, square_ep):
    with raises(WebSocketBadStatusException):
        ws_client_factory('/square')
    with server.patch_ws_endpoint(square_ep):
        ws_client = ws_client_factory('/square')
        ws_client.send('12')
        assert ws_client.recv() == '144'
        assert_ws_closed(ws_client)
    with raises(WebSocketBadStatusException):
        ws_client_factory('/square')
    with server.patch_ws_endpoint(square_ep):
        ws_client = ws_client_factory('/square')
        ws_client.send('12')
        assert ws_client.recv() == '144'
        assert_ws_closed(ws_client)
    with raises(WebSocketBadStatusException):
        ws_client_factory('/square')


def test_from_container(server, docker_client, create_and_pull):
    ep = server.add_http_endpoint('GET', '/foo', PlainTextResponse('hi'))
    with ep.capture_calls() as calls:
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv "{server.container_url()}/foo" --fail -X "GET"',
        )
        container.start()
        container.wait()
        container.reload()
        assert container.attrs['State']["ExitCode"] == 0
    calls.assert_requested_once()


def test_ws_capture_client_close(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint('/bar')
    async def bar(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text('do you like warhammer?')
        msg = await websocket.receive()
        assert msg['type'] == 'websocket.disconnect'

    with bar.capture_calls() as transcripts:
        ws_client = ws_client_factory('/bar')
        assert ws_client.recv() == 'do you like warhammer?'
        ws_client.close()

    sleep(0.1)  # give the server time to record the closing
    transcript, = transcripts
    assert list(transcript) == [
        RecordedWSMessage('do you like warhammer?', Sender.Server),
    ]
    assert transcript.accepted
    assert transcript.close == (Sender.Client, 1000)


def test_ws_patch(server, ws_calc, ws_client_factory):
    ws_client = ws_client_factory('/12/calc')
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
        await ws.send_text('no')
        return WS_1000_NORMAL_CLOSURE

    with ws_calc.patch(new_side_effect):
        ws_client = ws_client_factory('/12/calc')
        ws_client.send('{"op":"add", "value": 3}')
        assert ws_client.recv() == 'no'
        assert_ws_closed(ws_client)

    ws_client = ws_client_factory('/12/calc')
    assert json.loads(ws_client.recv()) == 12
    ws_client.send('{"op":"add", "value": 3}')
    assert json.loads(ws_client.recv()) == 15
    ws_client.send('{"op":"mul", "value": 10}')
    assert json.loads(ws_client.recv()) == 150
    ws_client.send('{"op":"done"}')
    assert_ws_closed(ws_client)


def test_ws_capture_no_accept(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint('/bar')
    async def bar(websocket: WebSocket):
        await websocket.close(WS_1008_POLICY_VIOLATION)

    with bar.capture_calls() as transcripts:
        with raises(WebSocketBadStatusException):
            ws_client_factory('/bar')

    sleep(0.1)  # give the server time to record the closing
    transcript, = transcripts
    assert list(transcript) == []
    assert not transcript.accepted
    assert transcript.close == (Sender.Server, 1008)


def test_ws_capture_empties(server, ws_client_factory):
    @server.add_ws_endpoint
    @ws_endpoint('/bar')
    async def bar(websocket: WebSocket):
        await websocket.accept()
        while True:
            msg = await websocket.receive()
            if msg['type'] == 'websocket.disconnect':
                return
            if 'text' in msg:
                await websocket.send_text(msg['text'])
            else:
                await websocket.send_bytes(msg['bytes'])

    with bar.capture_calls() as transcripts:
        ws_client = ws_client_factory('/bar')
        ws_client.send_binary(b'a')
        assert ws_client.recv() == b'a'
        ws_client.send_binary(b'')
        assert ws_client.recv() == b''
        ws_client.send('')
        assert ws_client.recv() == ''
        ws_client.send('a')
        assert ws_client.recv() == 'a'
        ws_client.close()

    t, = transcripts
    assert list(t) == [
        RecordedWSMessage(b'a', Sender.Client),
        RecordedWSMessage(b'a', Sender.Server),
        RecordedWSMessage(b'', Sender.Client),
        RecordedWSMessage(b'', Sender.Server),
        RecordedWSMessage('', Sender.Client),
        RecordedWSMessage('', Sender.Server),
        RecordedWSMessage('a', Sender.Client),
        RecordedWSMessage('a', Sender.Server),
    ]


def test_server_as_class():
    class CalculatorService(WebServer):
        square: MockHTTPEndpoint
        calc: MockWSEndpoint

        def start(self, retry_spec=None) -> WebServer:
            ret = super().start(retry_spec)

            async def square(request: Request):
                return PlainTextResponse(str(request.path_params['a'] ** 2))

            self.square = self.add_http_endpoint('GET', '/{a:int}/square', square)
            self.calc = self.add_ws_endpoint('/{a:int}/calc', do_some_math)
            return ret

    with CalculatorService('calulator').start() as server:
        with Client(base_url=server.local_url()) as client:
            with server.square.capture_calls() as calls:
                resp = client.get('/12/square')
                resp.raise_for_status()
                assert resp.text == '144'
            calls.assert_requested_once_with(path='/12/square')

        ws_client = create_ws_connection(server.local_url('ws') + '/12/calc?mod=20')
        assert json.loads(ws_client.recv()) == 12
        ws_client.send(json.dumps({'op': 'add', 'value': 1}))
        assert json.loads(ws_client.recv()) == 13
        ws_client.send(json.dumps({'op': 'mul', 'value': 15}))
        assert json.loads(ws_client.recv()) == 15
        ws_client.send(json.dumps({'op': 'done'}))


def test_server_class_endpoints():
    class CalculatorService(WebServer):
        @class_http_endpoint('GET', '/{a:int}/square')
        async def square(self, request: Request):
            return PlainTextResponse(str(request.path_params['a'] ** 2))

        @class_ws_endpoint('/{a:int}/calc')
        async def calc(self, websocket: WebSocket):
            return await do_some_math(websocket)

    with CalculatorService('calulator').start() as server:
        with Client(base_url=server.local_url()) as client:
            with server.square.capture_calls() as calls:
                resp = client.get('/12/square')
                resp.raise_for_status()
                assert resp.text == '144'
            calls.assert_requested_once_with(path='/12/square')

        ws_client = create_ws_connection(server.local_url('ws') + '/12/calc?mod=20')
        assert json.loads(ws_client.recv()) == 12
        ws_client.send(json.dumps({'op': 'add', 'value': 1}))
        assert json.loads(ws_client.recv()) == 13
        ws_client.send(json.dumps({'op': 'mul', 'value': 15}))
        assert json.loads(ws_client.recv()) == 15
        ws_client.send(json.dumps({'op': 'done'}))


def test_iter_side_effect(server, client):
    async def side_effect0(request: Request):
        return PlainTextResponse(str(int(request.query_params['x']) * 2))

    async def side_effect1(request: Request):
        return PlainTextResponse(str(int(request.query_params['x']) ** 2))

    side_effect2 = Response(status_code=526)

    async def side_effect3(request: Request):
        return PlainTextResponse(str(-int(request.query_params['x'])))

    server.add_http_endpoint('GET', '/foo', iter_side_effects([side_effect0, side_effect1, side_effect2, side_effect3]))

    resp = client.get('/foo?x=12')
    resp.raise_for_status()
    assert resp.text == '24'
    resp = client.get('/foo?x=12')
    resp.raise_for_status()
    assert resp.text == '144'
    resp = client.get('/foo?x=12')
    assert resp.status_code == 526
    resp = client.get('/foo?x=12')
    resp.raise_for_status()
    assert resp.text == '-12'


def test_two_servers():
    with WebServer('foo').start() as server1:
        with WebServer('bar').start() as server2:
            server1.add_http_endpoint('GET', '/foo', PlainTextResponse('foo'))

            @server2.add_http_endpoint
            @http_endpoint('GET', '/bar')
            async def bar(request: Request):
                resp = get(server1.local_url() + '/foo')
                resp.raise_for_status()
                return PlainTextResponse(resp.text + 'bar')

            resp = get(server2.local_url() + '/bar')
            resp.raise_for_status()
            assert resp.text == 'foobar'


def test_verbose_side_effect():
    with WebServer('my_foo').start() as server:
        file = StringIO()
        side_effect = verbose_http_side_effect(PlainTextResponse('foo'), file=file)
        server.add_http_endpoint('GET', '/foo', side_effect, name='foo')

        resp = get(server.local_url() + '/foo')
        resp.raise_for_status()
        assert resp.text == 'foo'

        resp = get(server.local_url() + '/foo', params={'x': '12'})
        resp.raise_for_status()
        assert resp.text == 'foo'

    assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} my_foo:foo [\d.]+:\d+ - GET /foo 200 \(3 bytes\)\n'
                        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} my_foo:foo [\d.]+:\d+ - GET /foo\?x=12 200 \(3 bytes\)\n',
                        file.getvalue())
