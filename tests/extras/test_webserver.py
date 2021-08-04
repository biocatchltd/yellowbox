from flask import Request
from httpx import Client
from yellowbox.extras.webserver import WebServer, MockHTTPEndpoint


def test_make_server():
    with WebServer('test').start():
        pass

def test_mock_response():
    with WebServer('test').start() as server:
        client = Client(base_url=server.local_url())
        endpoint = server.add_http_endpoint(MockHTTPEndpoint('test-1', 'GET', '/api/foo', side_effect='hewwo'))
        with endpoint.capture_calls() as calls:
            assert calls == []
            resp = client.get('/api/foo')
            assert resp.status_code == 200
            assert resp.text == 'hewwo'
            assert calls == [Request()]
