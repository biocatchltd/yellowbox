import json

from httpx import Client
from pytest import raises
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.websockets import WebSocket
from websocket import create_connection as create_ws_connection

from tests.extras.test_webserver.util import do_some_math
from yellowbox.extras.webserver import (
    MockHTTPEndpoint, MockWSEndpoint, WebServer, class_http_endpoint, class_ws_endpoint
)


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


def test_const_class_endpoint():
    class Server(WebServer):
        ping = class_http_endpoint('GET', '/health', Response())

    with Server('server').start() as server, server.ping.capture_calls() as calls:
        with Client(base_url=server.local_url()) as client:
            resp = client.get('/health')
            assert resp.status_code == 200
        calls.assert_requested_once_with(method='GET', path='/health')


def test_inline_ws_class_endpoint():
    class Server(WebServer):
        calc = class_ws_endpoint('/{a:int}/calc', staticmethod(do_some_math))

    with Server('server').start() as server:
        ws_client = create_ws_connection(server.local_url('ws') + '/12/calc?mod=10')
        assert json.loads(ws_client.recv()) == 2
        ws_client.send(json.dumps({'op': 'add', 'value': 1}))
        assert json.loads(ws_client.recv()) == 3
        ws_client.send(json.dumps({'op': 'mul', 'value': 15}))
        assert json.loads(ws_client.recv()) == 5
        ws_client.send(json.dumps({'op': 'done'}))


def test_class_endpoint_from_parents():
    class Server0(WebServer):
        @class_http_endpoint('GET', '/health')
        async def health(self, request):
            return PlainTextResponse('OK')

    class Server1(WebServer):
        @class_http_endpoint('GET', '/square')
        async def square(self, request):
            return PlainTextResponse(str(int(request.query_params['x']) ** 2))

    class Server2(Server0, Server1):
        @class_http_endpoint('GET', '/cube')
        async def cube(self, request):
            return PlainTextResponse(str(int(request.query_params['x']) ** 3))

    with Server2('').start() as server:
        with Client(base_url=server.local_url()) as client:
            resp = client.get('/health')
            resp.raise_for_status()
            assert resp.text == 'OK'

            resp = client.get('/square?x=2')
            resp.raise_for_status()
            assert resp.text == '4'

            resp = client.get('/cube?x=3')
            resp.raise_for_status()
            assert resp.text == '27'


def test_conflict_from_parents():
    class Server0(WebServer):
        @class_http_endpoint('GET', '/health')
        async def health(self, request):
            return PlainTextResponse('OK')

    class Server1(WebServer):
        @class_http_endpoint('GET', '/health')
        async def health(self, request):
            return PlainTextResponse('OK')

    with raises(TypeError):
        class Server(Server0, Server1):
            pass


def test_conflict_from_parent():
    class Server0(WebServer):
        @class_http_endpoint('GET', '/health')
        async def health(self, request):
            return PlainTextResponse('OK')

    with raises(TypeError):
        class Server1(Server0):
            @class_http_endpoint('GET', '/health')
            async def health(self, request):
                return PlainTextResponse('OK')
