import re
from urllib.parse import parse_qs

import requests
from pytest import mark

from yellowbox import connect, temp_network
from yellowbox.extras.http_server import HttpService, RouterHTTPRequestHandler


def test_make_server():
    with HttpService().start():
        pass


@mark.parametrize('method', ['GET', 'POST'])
def test_route_const(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + '/a/b/c').status_code == 404

        with service.patch_route(method, '/a/b/c', b'hello world'):
            response = requests.request(method, service.local_url + '/a/b/c')
            response.raise_for_status()
            assert response.content.strip() == b'hello world'

        assert requests.request(method, service.local_url + '/a/b/c').status_code == 404


@mark.parametrize('method', ['GET', 'PUT'])
def test_route_query(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + '/square').status_code == 404

        @service.patch_route(method, '/square')
        def square(request_handler: RouterHTTPRequestHandler):
            params = parse_qs(request_handler.parse_url().query)
            if 'n' not in params:
                return 400
            n = int(params['n'][0])
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + '/square?n=12')
            response.raise_for_status()
            assert response.content.strip() == b'144'

        assert requests.request(method, service.local_url + '/square').status_code == 404


@mark.parametrize('method', ['GET', 'POST'])
def test_from_container(create_and_pull, docker_client, method):
    with temp_network(docker_client) as network:
        with HttpService().start() as service, \
                connect(network, service) as aliases:
            url = f"http://{aliases[0]}:{service.server_port}"
            assert url == service.container_url
            container = create_and_pull(
                docker_client,
                "byrnedo/alpine-curl:latest", f'-vvv "{url}" --fail -X "{method}"',
                detach=True
            )
            with service.patch_route(method, '/', 200), \
                 connect(network, container):
                container.start()
                return_status = container.wait()
                assert return_status["StatusCode"] == 0


@mark.parametrize('method', ['GET', 'POST'])
def test_from_container_no_network(create_and_pull, docker_client, method):
    with HttpService().start() as service:
        url = service.container_url
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest", f'-vvv "{url}" --fail -X "{method}"',
            detach=True
        )
        with service.patch_route(method, '/', 200):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


@mark.parametrize('method', ['GET', 'PUT'])
def test_route_query_regex(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + '/square').status_code == 404

        @service.patch_route(method, re.compile('/square/([0-9]+)'))
        def square(request_handler: RouterHTTPRequestHandler):
            n = int(request_handler.match[1])
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + '/square/12')
            response.raise_for_status()
            assert response.content.strip() == b'144'

        assert requests.request(method, service.local_url + '/square').status_code == 404


@mark.parametrize('method', ['GET', 'PUT'])
def test_route_ambiguous(method):
    with HttpService().start() as service:
        with service.patch_route(method, re.compile('/[abc]'), '1'), \
             service.patch_route(method, re.compile('/[cde]'), '2'):
            assert requests.request(method, service.local_url + '/a').content == b'1'
            assert requests.request(method, service.local_url + '/d').content == b'2'
            assert requests.request(method, service.local_url + '/c').status_code == 500


@mark.parametrize('method', ['GET', 'PUT'])
def test_body(method):
    with HttpService().start() as service:
        @service.patch_route(method, '/square')
        def square(request_handler: RouterHTTPRequestHandler):
            try:
                n = int(str(request_handler.body(), 'ascii'))
            except ValueError:
                return 400
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + '/square', data=b'12')
            response.raise_for_status()
            assert response.content.strip() == b'144'


def test_session_const():
    with HttpService().start() as service:
        with service.patch_route('GET', '/hi', b'he\0llo'), \
             requests.Session() as session:
            assert session.get(service.local_url + '/hi').text == 'he\0llo'
            assert session.get(service.local_url + '/hi').text == 'he\0llo'
