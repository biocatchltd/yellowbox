import re
from urllib.parse import parse_qs

import requests
from pytest import mark

from yellowbox.extras.http_server import HttpService, RouterHTTPRequestHandler


def test_make_server():
    with HttpService().start():
        pass


@mark.parametrize("method", ["GET", "POST"])
def test_route_const(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + "/a/b/c").status_code == 404

        with service.patch_route(method, "/a/b/c", b"hello world"):
            response = requests.request(method, service.local_url + "/a/b/c")
            response.raise_for_status()
            assert response.content.strip() == b"hello world"

        assert requests.request(method, service.local_url + "/a/b/c").status_code == 404


@mark.parametrize("method", ["GET", "PUT"])
def test_route_query(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + "/square").status_code == 404

        @service.patch_route(method, "/square")
        def square(request_handler: RouterHTTPRequestHandler):
            params = parse_qs(request_handler.parse_url().query)
            if "n" not in params:
                return 400
            n = int(params["n"][0])
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + "/square?n=12")
            response.raise_for_status()
            assert response.content.strip() == b"144"

        assert requests.request(method, service.local_url + "/square").status_code == 404


@mark.parametrize("method", ["GET", "POST"])
def test_from_container(create_and_pull, docker_client, method):
    with HttpService().start() as service:
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv "{service.container_url}" --fail -X "{method}"',
            detach=True,
        )
        with service.patch_route(method, "/", 200):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


@mark.parametrize("method", ["GET", "PUT"])
def test_route_query_regex(method):
    with HttpService().start() as service:
        assert requests.request(method, service.local_url + "/square").status_code == 404

        @service.patch_route(method, re.compile("/square/([0-9]+)"))
        def square(request_handler: RouterHTTPRequestHandler):
            n = int(request_handler.match[1])
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + "/square/12")
            response.raise_for_status()
            assert response.content.strip() == b"144"

        assert requests.request(method, service.local_url + "/square").status_code == 404


@mark.parametrize("method", ["GET", "PUT"])
def test_route_ambiguous(method):
    with HttpService().start() as service, service.patch_route(method, re.compile("/[abc]"), "1"), service.patch_route(
        method, re.compile("/[cde]"), "2"
    ):
        assert requests.request(method, service.local_url + "/a").content == b"1"
        assert requests.request(method, service.local_url + "/d").content == b"2"
        assert requests.request(method, service.local_url + "/c").status_code == 500


@mark.parametrize("method", ["GET", "PUT"])
def test_body(method):
    with HttpService().start() as service:

        @service.patch_route(method, "/square")
        def square(request_handler: RouterHTTPRequestHandler):
            try:
                n = int(str(request_handler.body(), "ascii"))
            except ValueError:
                return 400
            return str(n * n)

        with square:
            response = requests.request(method, service.local_url + "/square", data=b"12")
            response.raise_for_status()
            assert response.content.strip() == b"144"


def test_session_const():
    with HttpService().start() as service, service.patch_route("GET", "/hi", b"he\0llo"), requests.Session() as session:
        assert session.get(service.local_url + "/hi").content == b"he\0llo"
        assert session.get(service.local_url + "/hi").content == b"he\0llo"


def test_get_params():
    with HttpService().start() as service:

        @service.patch_route("GET", "/square")
        def square(request_handler: RouterHTTPRequestHandler):
            assert request_handler.body() is None
            try:
                n = int(request_handler.path_params()["n"][0])
            except ValueError:
                return 400
            return str(n * n)

        with square:
            response = requests.get(service.local_url + "/square", params={"n": "12"})
        response.raise_for_status()
        assert response.content.strip() == b"144"


def test_handle_request_manually(monkeypatch):
    with HttpService().start() as service:

        @service.patch_route("GET", "/square")
        def square(request_handler: RouterHTTPRequestHandler):
            request_handler.send_response(200)
            request_handler.send_header("test", "1")
            request_handler.end_headers()
            return request_handler

        with square:
            response = requests.get(service.local_url + "/square")
        assert response.headers["test"] == "1"
