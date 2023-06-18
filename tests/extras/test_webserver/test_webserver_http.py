import re
from io import StringIO

from httpx import Client, HTTPError, get
from pytest import raises
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from yellowbox.extras.webserver import WebServer, http_endpoint, iter_side_effects, verbose_http_side_effect
from yellowbox.extras.webserver.webserver import HandlerError


def test_mock_callable(server, client):
    @server.add_http_endpoint
    @http_endpoint("POST", "/{a:int}/foo")
    async def get_foo(request: Request):
        a = request.path_params["a"]
        b = await request.json()
        return JSONResponse(a * b)

    resp = client.post("/12/foo", json=15)
    resp.raise_for_status()
    assert resp.json() == 15 * 12

    with get_foo.patch(JSONResponse(["a", "b"])):
        resp = client.post("/12/foo", json=15)
        resp.raise_for_status()
        assert resp.json() == ["a", "b"]

    resp = client.post("/12/foo", json=10)
    resp.raise_for_status()
    assert resp.json() == 10 * 12


def test_capture(server, client):
    endpoint = server.add_http_endpoint("GET", "/api/foo", side_effect=PlainTextResponse("hewwo"))
    with endpoint.capture_calls() as calls0:
        assert calls0 == []

        with endpoint.capture_calls() as calls1:
            assert calls1 == []
            resp = client.get("/api/foo?a=15&a=17")
            assert resp.status_code == 200
            assert resp.text == "hewwo"

        (c1,) = calls1
        assert c1.method == "GET"
        assert c1.path == "/api/foo"
        assert c1.path_params == {}
        assert c1.query_params == {"a": ["15", "17"]}

        resp = client.get("/api/foo")
        assert resp.status_code == 200
        assert resp.text == "hewwo"
    c0_0, c0_1 = calls0
    assert c0_0 == c1


def test_remove_path():
    with WebServer("test").start() as server:
        client = Client(base_url=server.local_url())

        @http_endpoint("POST", "/{a:int}/foo")
        async def get_foo(request):
            a = request.path_params["a"]
            b = await request.json()
            return JSONResponse(a * b)

        assert client.post("/12/foo", json=15).status_code == HTTP_404_NOT_FOUND
        assert client.post("/12/bar", json=15).status_code == HTTP_404_NOT_FOUND

        with server.patch_http_endpoint(get_foo):
            resp = client.post("/12/foo", json=15)
            resp.raise_for_status()
            assert resp.json() == 15 * 12

        assert client.post("/12/foo", json=15).status_code == HTTP_404_NOT_FOUND
        assert client.post("/12/bar", json=15).status_code == HTTP_404_NOT_FOUND
    with raises(HTTPError):
        client.post("/12/foo", json=15)


def test_multi_paths(server, client):
    with server.patch_http_endpoint("GET", "/foo", PlainTextResponse("hi")):
        resp = client.get("/foo")
        resp.raise_for_status()
        assert resp.text == "hi"
        with server.patch_http_endpoint("GET", "/bar", PlainTextResponse("ho")):
            resp = client.get("/foo")
            resp.raise_for_status()
            assert resp.text == "hi"
            resp = client.get("/bar")
            resp.raise_for_status()
            assert resp.text == "ho"
        resp = client.get("/foo")
        resp.raise_for_status()
        assert resp.text == "hi"
        assert client.get("/bar").status_code == HTTP_404_NOT_FOUND


def test_readd_endpoint(server, client):
    ep = http_endpoint("GET", "/foo", PlainTextResponse("hi"))
    assert client.get("/foo").status_code == HTTP_404_NOT_FOUND
    with server.patch_http_endpoint(ep):
        resp = client.get("/foo")
        resp.raise_for_status()
        assert resp.text == "hi"
    assert client.get("/foo").status_code == HTTP_404_NOT_FOUND
    with server.patch_http_endpoint(ep):
        resp = client.get("/foo")
        resp.raise_for_status()
        assert resp.text == "hi"
    assert client.get("/foo").status_code == HTTP_404_NOT_FOUND


def test_handler_error(server, client, squib):
    assert client.get("/bar").status_code == HTTP_500_INTERNAL_SERVER_ERROR
    with raises(HandlerError) as exc_info:
        server.is_alive()
    cause = exc_info.value.__cause__
    assert isinstance(cause, ValueError)
    assert cause.args == ("ree",)


def test_handler_error_stuck(server, client, squib):
    server.add_http_endpoint("GET", "/foo", PlainTextResponse("voodoo"))
    assert client.get("/foo").status_code == HTTP_200_OK
    assert client.get("/bar").status_code == HTTP_500_INTERNAL_SERVER_ERROR
    resp = client.get("/foo")
    assert resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert "ValueError('ree')" in resp.text
    with raises(HandlerError):
        server.is_alive()


def test_methods(server, client):
    server.add_http_endpoint(("POST", "GET"), "/foo", PlainTextResponse("voodoo"))
    resp = client.post("/foo")
    resp.raise_for_status()
    assert resp.text == "voodoo"
    resp = client.get("/foo")
    resp.raise_for_status()
    assert resp.text == "voodoo"

    assert client.put("/foo").status_code == 405
    assert client.head("/foo").status_code == 405


def test_methods_with_head(server, client):
    server.add_http_endpoint(("POST", "GET"), "/foo", PlainTextResponse("voodoo"), forbid_implicit_head_verb=False)
    resp = client.post("/foo")
    resp.raise_for_status()
    assert resp.text == "voodoo"
    resp = client.get("/foo")
    resp.raise_for_status()
    assert resp.text == "voodoo"
    resp = client.head("/foo")
    resp.raise_for_status()
    assert not resp.content

    assert client.put("/foo").status_code == 405


def test_no_auto_read(server, client):
    ep = server.add_http_endpoint("GET", "/foo", PlainTextResponse("voodoo"), auto_read_body=False)
    resp = client.get("/foo")
    resp.raise_for_status()
    assert resp.text == "voodoo"

    with raises(RuntimeError), ep.capture_calls():
        ...


def test_parallel_capture(server):
    ep = server.add_http_endpoint("GET", "/foo", PlainTextResponse("voodoo"))
    con1 = ep.capture_calls()
    con2 = ep.capture_calls()

    with raises(RuntimeError), con1:
        con2.__enter__()


def test_from_container(server, docker_client, create_and_pull):
    ep = server.add_http_endpoint("GET", "/foo", PlainTextResponse("hi"))
    with ep.capture_calls() as calls:
        container = create_and_pull(
            docker_client,
            "byrnedo/alpine-curl:latest",
            f'-vvv "{server.container_url()}/foo" --fail -X "GET"',
        )
        container.start()
        container.wait()
        container.reload()
        assert container.attrs["State"]["ExitCode"] == 0
    calls.assert_requested_once()


def test_iter_side_effect(server, client):
    async def side_effect0(request: Request):
        return PlainTextResponse(str(int(request.query_params["x"]) * 2))

    async def side_effect1(request: Request):
        return PlainTextResponse(str(int(request.query_params["x"]) ** 2))

    side_effect2 = Response(status_code=526)

    async def side_effect3(request: Request):
        return PlainTextResponse(str(-int(request.query_params["x"])))

    server.add_http_endpoint("GET", "/foo", iter_side_effects([side_effect0, side_effect1, side_effect2, side_effect3]))

    resp = client.get("/foo?x=12")
    resp.raise_for_status()
    assert resp.text == "24"
    resp = client.get("/foo?x=12")
    resp.raise_for_status()
    assert resp.text == "144"
    resp = client.get("/foo?x=12")
    assert resp.status_code == 526
    resp = client.get("/foo?x=12")
    resp.raise_for_status()
    assert resp.text == "-12"


def test_two_servers():
    with WebServer("foo").start() as server1, WebServer("bar").start() as server2:
        server1.add_http_endpoint("GET", "/foo", PlainTextResponse("foo"))

        @server2.add_http_endpoint
        @http_endpoint("GET", "/bar")
        async def bar(request: Request):
            resp = get(server1.local_url() + "/foo")
            resp.raise_for_status()
            return PlainTextResponse(resp.text + "bar")

        resp = get(server2.local_url() + "/bar")
        resp.raise_for_status()
        assert resp.text == "foobar"


def test_verbose_side_effect():
    with WebServer("my_foo").start() as server:
        file = StringIO()
        side_effect = verbose_http_side_effect(PlainTextResponse("foo"), file=file)
        server.add_http_endpoint("GET", "/foo", side_effect, name="foo")

        resp = get(server.local_url() + "/foo")
        resp.raise_for_status()
        assert resp.text == "foo"

        resp = get(server.local_url() + "/foo", params={"x": "12"})
        resp.raise_for_status()
        assert resp.text == "foo"

    # <date> <time> <server name>:<endpoint name> <client_ip>:<client_port> - <method> <path> <status code>
    # <response size>
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} my_foo:foo [\d.]+:\d+ - GET /foo 200 \(3 bytes\)\n"
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} my_foo:foo [\d.]+:\d+ - GET /foo\?x=12 200 \(3 bytes\)\n",
        file.getvalue(),
    )
