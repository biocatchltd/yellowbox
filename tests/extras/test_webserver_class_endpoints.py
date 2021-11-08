import json

from httpx import Client
from starlette.responses import Response, PlainTextResponse
from pytest import raises
from tests.extras.test_webserver import do_some_math
from yellowbox.extras.webserver import WebServer, class_ws_endpoint
from yellowbox.extras.webserver.class_endpoint import class_http_endpoint

from websocket import create_connection as create_ws_connection


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