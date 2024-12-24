import re
from datetime import datetime
from unittest.mock import MagicMock

from pytest import fixture, mark, raises

from yellowbox.extras.webserver.http_request_capture import (
    ExpectedHTTPRequest,
    RecordedHTTPRequest,
    RecordedHTTPRequests,
)
from yellowbox.extras.webserver.request_capture import _is_submap_of, _is_submultimap_of
from yellowbox.extras.webserver.ws_request_capture import (
    ExpectedWSTranscript,
    RecordedWSMessage,
    RecordedWSTranscript,
    RecordedWSTranscripts,
    Sender,
)


@mark.parametrize(
    "other",
    [
        {"a": 1, "b": 2},
        {"a": 1, "b": 2, "c": 7},
        {"a": 1, "b": 2, "c": 7, "d": object()},
    ],
)
def test_atleast_eq(other):
    al = {"a": 1, "b": 2}
    assert _is_submap_of(al, other)


@mark.parametrize(
    "other",
    [
        {},
        {"a": 1},
        {"b": 2, "c": 7},
        {"a": 11, "b": 2},
        {"a": 1, "b": 12},
    ],
)
def test_atleast_ne(other):
    al = {"a": 1, "b": 2}
    assert not _is_submap_of(al, other)


@mark.parametrize(
    "other",
    [
        {"a": {1, 11}, "b": {2, 22}, "d": set()},
        {"a": [1, 11, 13], "b": {2, 22}, "d": set()},
        {"a": {1, 11, 13}, "b": {2, 22, 23}, "d": {None}},
        {"a": {1, 11, 13}, "b": {2, 22, 23}, "c": {}, "d": {None}},
    ],
)
def test_atleastmulti_eq(other):
    al = {"a": {1, 11}, "b": {2, 22}, "d": frozenset()}
    assert _is_submultimap_of(al, other)


@mark.parametrize(
    "other",
    [
        {},
        {"a": 1, "b": 1, "c": 1},
        {"a": {1, 11}, "b": {2}, "d": set()},
        {"a": {1, 11}, "b": {2, 22}, "e": 15},
    ],
)
def test_atleastmulti_ne(other):
    al = {"a": {1, 11}, "b": {2, 22}, "d": frozenset()}
    assert not _is_submultimap_of(al, other)


@mark.parametrize(
    "other",
    [
        {"a": [1, 2, 1, 11], "b": {2, 22}},
        {"a": [2, 1, 1, 11], "b": {2, 22}},
    ],
)
def test_atleastmulti_multi_eq(other):
    al = {
        "a": [1, 1, 2],
    }
    assert _is_submultimap_of(al, other)


@mark.parametrize(
    "other",
    [
        {"a": [1, 2]},
        {"a": [2, 1]},
        {"a": [1, 1]},
    ],
)
def test_atleastmulti_multi_ne(other):
    al = {
        "a": [1, 1, 2],
    }
    assert not _is_submultimap_of(al, other)


@mark.parametrize(
    "expected",
    [
        ExpectedHTTPRequest(),
        ExpectedHTTPRequest(headers_submap={"c": ["3"]}),
        ExpectedHTTPRequest(method="GET"),
        ExpectedHTTPRequest(path="/foo/12/bar"),
        ExpectedHTTPRequest(path=re.compile("/foo/[0-9]+/bar")),
        ExpectedHTTPRequest(path_params={"x": 12}),
        ExpectedHTTPRequest(path_params_submap={"x": 12}),
        ExpectedHTTPRequest(query_params={"y": ["15", "17"]}),
        ExpectedHTTPRequest(query_params_submap={"y": ["15"]}),
        ExpectedHTTPRequest(body=b"15"),
        ExpectedHTTPRequest(text="15"),
        ExpectedHTTPRequest(json=15),
        ExpectedHTTPRequest(content_predicate=(int, 15)),
        ExpectedHTTPRequest(content_predicate=lambda x: x.startswith(b"1")),
    ],
)
def test_match_recorded_http_call(expected):
    recorded = RecordedHTTPRequest(
        {"a": ["1"], "b": ["2"], "c": ["3", "4"]},
        "GET",
        "/foo/12/bar",
        {"x": 12},
        {"y": ["15", "17"]},
        b"15",
        datetime.now(),
    )

    assert expected.matches(recorded)


@mark.parametrize(
    "expected",
    [
        ExpectedHTTPRequest(json_submap={}),
        ExpectedHTTPRequest(json_submap={"a": 15}),
        ExpectedHTTPRequest(json_submap={"a": 15, "b": "hi"}),
        ExpectedHTTPRequest(json_submap={"a": 15, "b": "hi", "c": [1, 2, "f"]}),
    ],
)
def test_match_recorded_http_call_json(expected):
    recorded = RecordedHTTPRequest(
        {"a": ["1"], "b": ["2"], "c": ["3", "4"]},
        "GET",
        "/foo/12/bar",
        {"x": 12},
        {"y": ["15", "17"]},
        b'{"a": 15, "b": "hi", "c":[1,2,"f"]}',
        datetime.now(),
    )

    assert expected.matches(recorded)


@mark.parametrize(
    "expected",
    [
        ExpectedHTTPRequest(headers_submap={"c": ["3", "10"]}),
        ExpectedHTTPRequest(headers={"c": ["3"]}),
        ExpectedHTTPRequest(method="PUT"),
        ExpectedHTTPRequest(path="/foo/12/bar/"),
        ExpectedHTTPRequest(path=re.compile("/foo/[0-1]+/bar")),
        ExpectedHTTPRequest(path_params={"t": 12}),
        ExpectedHTTPRequest(path_params_submap={"t": 12}),
        ExpectedHTTPRequest(query_params_submap={"y": ["15", "16"]}),
        ExpectedHTTPRequest(query_params={"y": ["15"]}),
        ExpectedHTTPRequest(body=b"25"),
        ExpectedHTTPRequest(text="16"),
        ExpectedHTTPRequest(json=11),
        ExpectedHTTPRequest(json_submap={"a": 11}),
        ExpectedHTTPRequest(content_predicate=(int, 12)),
        ExpectedHTTPRequest(content_predicate=lambda x: x.startswith(b"2")),
    ],
)
def test_mismatch_recorded_http_call(expected):
    recorded = RecordedHTTPRequest(
        {"a": ["1"], "b": ["2"], "c": ["3", "4"]},
        "GET",
        "/foo/12/bar",
        {"x": 12},
        {"y": ["15", "17"]},
        b"15",
        datetime.now(),
    )

    assert not expected.matches(recorded)


@mark.parametrize(
    ("expected", "repr_"),
    [
        (ExpectedHTTPRequest(), """ExpectedHTTPRequest()"""),
        (ExpectedHTTPRequest(headers={"c": ["3"]}), """ExpectedHTTPRequest(headers={'c': ['3']})"""),
        (ExpectedHTTPRequest(headers_submap={"c": ["3"]}), """ExpectedHTTPRequest(headers_submap={'c': ['3']})"""),
        (ExpectedHTTPRequest(method="GET"), """ExpectedHTTPRequest(method='GET')"""),
        (ExpectedHTTPRequest(path="/foo/12/bar"), """ExpectedHTTPRequest(path=re.compile('/foo/12/bar'))"""),
        (
            ExpectedHTTPRequest(path=re.compile("/foo/[0-9]+/bar")),
            """ExpectedHTTPRequest(path=re.compile('/foo/[0-9]+/bar'))""",
        ),
        (ExpectedHTTPRequest(path_params_submap={"x": 12}), """ExpectedHTTPRequest(path_params_submap={'x': 12})"""),
        (
            ExpectedHTTPRequest(query_params_submap={"y": ["15"]}),
            """ExpectedHTTPRequest(query_params_submap={'y': ['15']})""",
        ),
        (ExpectedHTTPRequest(body=b"15"), """ExpectedHTTPRequest(body=b'15')"""),
        (ExpectedHTTPRequest(text="15"), """ExpectedHTTPRequest(text='15')"""),
        (ExpectedHTTPRequest(json=15), """ExpectedHTTPRequest(json=15)"""),
        (
            ExpectedHTTPRequest(content_predicate=(int, 15)),
            """ExpectedHTTPRequest(content_predicate=(<class 'int'>, 15))""",
        ),
        (
            ExpectedHTTPRequest(headers_submap={"c": ["3", "10"]}),
            """ExpectedHTTPRequest(headers_submap={'c': ['3', '10']})""",
        ),
        (ExpectedHTTPRequest(method="PUT"), """ExpectedHTTPRequest(method='PUT')"""),
        (ExpectedHTTPRequest(path="/foo/12/bar/"), """ExpectedHTTPRequest(path=re.compile('/foo/12/bar/'))"""),
        (
            ExpectedHTTPRequest(path=re.compile("/foo/[0-1]+/bar")),
            """ExpectedHTTPRequest(path=re.compile('/foo/[0-1]+/bar'))""",
        ),
        (ExpectedHTTPRequest(path_params_submap={"t": 12}), """ExpectedHTTPRequest(path_params_submap={'t': 12})"""),
        (
            ExpectedHTTPRequest(query_params_submap={"y": ["15", "16"]}),
            """ExpectedHTTPRequest(query_params_submap={'y': ['15', '16']})""",
        ),
        (ExpectedHTTPRequest(body=b"25"), """ExpectedHTTPRequest(body=b'25')"""),
        (ExpectedHTTPRequest(text="16"), """ExpectedHTTPRequest(text='16')"""),
        (ExpectedHTTPRequest(json=11), """ExpectedHTTPRequest(json=11)"""),
        (
            ExpectedHTTPRequest(content_predicate=(int, 12)),
            """ExpectedHTTPRequest(content_predicate=(<class 'int'>, 12))""",
        ),
    ],
)
def test_expected_repr(expected, repr_):
    assert repr_ == str(expected)
    assert str(expected) == repr(expected)


def test_http_requests_empty():
    requests = RecordedHTTPRequests()
    requests.assert_not_requested()
    with raises(AssertionError):
        requests.assert_requested()
    with raises(AssertionError):
        requests.assert_requested_once()
    with raises(AssertionError):
        requests.assert_requested_with(body=b"")
    with raises(AssertionError):
        requests.assert_requested_once_with(body=b"")
    with raises(AssertionError):
        requests.assert_any_request(body=b"")
    with raises(AssertionError):
        requests.assert_has_requests(ExpectedHTTPRequest(body=b""))


def test_http_requests_many():
    requests = RecordedHTTPRequests(
        [
            RecordedHTTPRequest({}, "GET", "/bar", {}, {}, b"0", datetime.now()),
            RecordedHTTPRequest({}, "GET", "/bar", {}, {}, b"1", datetime.now()),
            RecordedHTTPRequest({}, "GET", "/bar", {}, {}, b"2", datetime.now()),
        ]
    )
    with raises(AssertionError):
        requests.assert_not_requested()
    requests.assert_requested()
    with raises(AssertionError):
        requests.assert_requested_once()
    requests.assert_requested_with(body=b"2")
    with raises(AssertionError):
        requests.assert_requested_with(body=b"3")
    with raises(AssertionError):
        requests.assert_requested_with(body=b"1")
    with raises(AssertionError):
        requests.assert_requested_once_with(body=b"2")
    requests.assert_any_request(body=b"0")
    requests.assert_any_request(body=b"1")
    requests.assert_any_request(body=b"2")
    with raises(AssertionError):
        requests.assert_any_request(body=b"3")
    requests.assert_has_requests(
        ExpectedHTTPRequest(body=b"0"),
        ExpectedHTTPRequest(body=b"2"),
    )
    with raises(AssertionError):
        requests.assert_has_requests(
            ExpectedHTTPRequest(body=b"1"),
            ExpectedHTTPRequest(body=b"0"),
            ExpectedHTTPRequest(body=b"2"),
        )
    with raises(AssertionError):
        requests.assert_has_requests(ExpectedHTTPRequest(body=b"3"))


def test_http_requests_one():
    requests = RecordedHTTPRequests(
        [
            RecordedHTTPRequest({}, "GET", "/bar", {}, {}, b"0", datetime.now()),
        ]
    )
    with raises(AssertionError):
        requests.assert_not_requested()
    requests.assert_requested()
    requests.assert_requested_once()
    requests.assert_requested_with(body=b"0")
    with raises(AssertionError):
        requests.assert_requested_with(body=b"3")
    with raises(AssertionError):
        requests.assert_requested_with(body=b"1")
    requests.assert_requested_once_with(body=b"0")
    with raises(AssertionError):
        requests.assert_requested_once_with(body=b"2")
    requests.assert_any_request(body=b"0")
    with raises(AssertionError):
        requests.assert_any_request(body=b"3")
    requests.assert_has_requests(
        ExpectedHTTPRequest(body=b"0"),
    )
    with raises(AssertionError):
        requests.assert_has_requests(
            ExpectedHTTPRequest(body=b"1"),
        )
    with raises(AssertionError):
        requests.assert_has_requests(ExpectedHTTPRequest(body=b"3"))


@fixture
def connection():
    ret = MagicMock()
    ret.headers.raw = []
    ret.url.path = ""
    ret.path_params = {}
    ret.query_params.multi_items.return_value = []
    return ret


def test_repr_transcript(connection):
    transcript = RecordedWSTranscript.from_connection(connection)
    transcript.extend(
        [
            RecordedWSMessage("sir if I may be so bold?", Sender.Server, datetime.now()),
            RecordedWSMessage("go ahead Jeeves", Sender.Client, datetime.now()),
            RecordedWSMessage(b"crunch", Sender.Server, datetime.now()),
            RecordedWSMessage("Jeeves! That is bold", Sender.Client, datetime.now()),
        ]
    )
    assert (
        repr(transcript) == "[RecordedWSMessage('sir if I may be so bold?', Sender.Server),"
        " RecordedWSMessage('go ahead Jeeves', Sender.Client),"
        " RecordedWSMessage(b'crunch', Sender.Server),"
        " RecordedWSMessage('Jeeves! That is bold', Sender.Client)]"
    )


@mark.parametrize(
    ("close", "expected_close"),
    [
        ((Sender.Server, 1000), None),
        ((Sender.Server, 1000), (Sender.Server, 1000)),
        ((Sender.Client, 1000), None),
        ((Sender.Client, 1000), (Sender.Client, 1000)),
    ],
)
@mark.parametrize(
    ("accepted", "expected_accepted"),
    [
        (True, None),
        (False, None),
        (True, True),
        (False, False),
    ],
)
def test_transcript_matches(close, expected_close, accepted, expected_accepted, connection):
    transcript = RecordedWSTranscript.from_connection(connection)
    transcript.extend(
        [
            RecordedWSMessage("sir if I may be so bold?", Sender.Server, datetime.now()),
            RecordedWSMessage("go ahead Jeeves", Sender.Client, datetime.now()),
            RecordedWSMessage(b"crunch", Sender.Server, datetime.now()),
            RecordedWSMessage("Jeeves! That is bold", Sender.Client, datetime.now()),
        ]
    )
    transcript.accepted = accepted
    transcript.close = close

    expected = ExpectedWSTranscript(
        [..., Sender.Client("go ahead Jeeves"), Sender.Server(re.compile(b"crun[ct]h")), ...],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [Sender.Server(...), Sender.Client("go ahead Jeeves"), ...], close=expected_close, accepted=expected_accepted
    )
    assert expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [..., Sender.Server(re.compile(b"crun[ct]h")), Sender.Client("Jeeves! That is bold")],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [
            Sender.Server(...),
            Sender.Client("go ahead Jeeves"),
            Sender.Server(re.compile(b"crun[ct]h")),
            Sender.Client("Jeeves! That is bold"),
        ],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert expected.matches(transcript)
    expected = ExpectedWSTranscript([...], close=expected_close, accepted=expected_accepted)
    assert expected.matches(transcript)


@mark.parametrize(
    ("close", "expected_close", "accepted", "expected_accepted"),
    [
        ((Sender.Server, 1000), (Sender.Client, 1000), True, None),
        ((Sender.Client, 1000), (Sender.Server, 1000), True, None),
        ((Sender.Server, 1000), (Sender.Server, 1001), True, None),
        ((Sender.Server, 1001), (Sender.Server, 1000), True, None),
        ((Sender.Client, 1000), (Sender.Client, 1001), True, None),
        ((Sender.Client, 1001), (Sender.Client, 1000), True, None),
        ((Sender.Server, 1000), None, True, False),
        ((Sender.Server, 1000), None, False, True),
    ],
)
def test_transcript_mismatches(close, expected_close, accepted, expected_accepted, connection):
    transcript = RecordedWSTranscript.from_connection(connection)
    transcript.extend(
        [
            RecordedWSMessage("sir if I may be so bold?", Sender.Server, datetime.now()),
            RecordedWSMessage("go ahead Jeeves", Sender.Client, datetime.now()),
            RecordedWSMessage(b"crunch", Sender.Server, datetime.now()),
            RecordedWSMessage("Jeeves! That is bold", Sender.Client, datetime.now()),
        ]
    )
    transcript.accepted = accepted
    transcript.close = close

    expected = ExpectedWSTranscript(
        [..., Sender.Client("go ahead Jeeves"), Sender.Server(re.compile(b"crun[ct]h")), ...],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [Sender.Server(...), Sender.Client("go ahead Jeeves"), ...], close=expected_close, accepted=expected_accepted
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [..., Sender.Server(re.compile(b"crun[ct]h")), Sender.Client("Jeeves! That is bold")],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [
            Sender.Server(...),
            Sender.Client("go ahead Jeeves"),
            Sender.Server(re.compile(b"crun[ct]h")),
            Sender.Client("Jeeves! That is bold"),
        ],
        close=expected_close,
        accepted=expected_accepted,
    )
    assert not expected.matches(transcript)


def test_transcript_mismatches_body(connection):
    connection.headers.raw = [("a", "1"), ("b", "1"), ("a", "2")]
    connection.url.path = "/foobar"
    connection.path_params = {"x": 15}
    connection.query_params.multi_items.return_value = [("s", "1"), ("r", "1"), ("s", "2")]
    transcript = RecordedWSTranscript.from_connection(connection)
    transcript.extend(
        [
            RecordedWSMessage("sir if I may be so bold?", Sender.Server, datetime.now()),
            RecordedWSMessage("go ahead Jeeves", Sender.Client, datetime.now()),
            RecordedWSMessage(b"crunch", Sender.Server, datetime.now()),
            RecordedWSMessage("Jeeves! That is bold", Sender.Client, datetime.now()),
        ]
    )
    transcript.close = True
    transcript.accepted = True

    expected = ExpectedWSTranscript(
        [..., Sender.Server(re.compile(b"crun[ct]e")), ...],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [..., Sender.Server(...), Sender.Client("go ahead Jeeves")],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [Sender.Server(re.compile(b"crun[ct]h")), Sender.Client("Jeeves! That is bold"), ...],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [
            Sender.Client("go ahead Jeeves"),
            Sender.Server(re.compile(b"crun[ct]h")),
            Sender.Client("Jeeves! That is bold"),
        ],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [
            ...,
            Sender.Server(...),
            Sender.Client(...),
            Sender.Server(...),
            Sender.Client(...),
            Sender.Server(...),
            Sender.Client(...),
            ...,
        ],
    )
    assert not expected.matches(transcript)


def test_transcript_mismatches_scope(connection):
    connection.headers.raw = [("a", "1"), ("b", "1"), ("a", "2")]
    connection.url.path = "/foobar"
    connection.path_params = {"x": 15}
    connection.query_params.multi_items.return_value = [("s", "1"), ("r", "1"), ("s", "2")]
    transcript = RecordedWSTranscript.from_connection(connection)
    transcript.extend(
        [
            RecordedWSMessage("sir if I may be so bold?", Sender.Server, datetime.now()),
            RecordedWSMessage("go ahead Jeeves", Sender.Client, datetime.now()),
            RecordedWSMessage(b"crunch", Sender.Server, datetime.now()),
            RecordedWSMessage("Jeeves! That is bold", Sender.Client, datetime.now()),
        ]
    )
    transcript.close = True
    transcript.accepted = True

    expected = ExpectedWSTranscript([...], headers_submap={"a": {"1", "3"}})
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [..., Sender.Server(...), Sender.Client("go ahead Jeeves")],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [Sender.Server(re.compile(b"crun[ct]h")), Sender.Client("Jeeves! That is bold"), ...],
    )
    assert not expected.matches(transcript)
    expected = ExpectedWSTranscript(
        [
            Sender.Client("go ahead Jeeves"),
            Sender.Server(re.compile(b"crun[ct]h")),
            Sender.Client("Jeeves! That is bold"),
        ],
    )
    assert not expected.matches(transcript)


def test_transcripts_empty():
    transcripts = RecordedWSTranscripts()
    transcripts.assert_not_requested()
    with raises(AssertionError):
        transcripts.assert_requested()
    with raises(AssertionError):
        transcripts.assert_requested_once()
    with raises(AssertionError):
        transcripts.assert_requested_with(ExpectedWSTranscript([...]))
    with raises(AssertionError):
        transcripts.assert_requested_once_with(ExpectedWSTranscript([...]))
    with raises(AssertionError):
        transcripts.assert_any_request(ExpectedWSTranscript([...]))


def test_transcripts_multi(connection):
    t0 = RecordedWSTranscript.from_connection(connection)
    t0.append(RecordedWSMessage("hi", Sender.Server, datetime.now()))
    t1 = RecordedWSTranscript.from_connection(connection)
    t1.append(RecordedWSMessage("ho", Sender.Server, datetime.now()))
    t0.close = t1.close = (Sender.Server, 1000)
    t0.accepted = t1.accepted = True
    transcripts = RecordedWSTranscripts([t0, t1])
    with raises(AssertionError):
        transcripts.assert_not_requested()
    transcripts.assert_requested()
    with raises(AssertionError):
        transcripts.assert_requested_once()
    transcripts.assert_requested_with(ExpectedWSTranscript([..., Sender.Server("ho")]))
    with raises(AssertionError):
        transcripts.assert_requested_with(ExpectedWSTranscript([..., Sender.Server("hi")]))
    with raises(AssertionError):
        transcripts.assert_requested_once_with(ExpectedWSTranscript([...]))
    transcripts.assert_any_request(ExpectedWSTranscript([..., Sender.Server("hi")]))
    transcripts.assert_any_request(ExpectedWSTranscript([..., Sender.Server("ho")]))
    with raises(AssertionError):
        transcripts.assert_any_request(ExpectedWSTranscript([..., Sender.Server("hee")]))


def test_transcripts_single(connection):
    t0 = RecordedWSTranscript.from_connection(connection)
    t0.append(RecordedWSMessage("hi", Sender.Server, datetime.now()))
    t0.close = (Sender.Server, 1000)
    t0.accepted = True
    transcripts = RecordedWSTranscripts([t0])
    with raises(AssertionError):
        transcripts.assert_not_requested()
    transcripts.assert_requested()
    transcripts.assert_requested_once()
    transcripts.assert_requested_with(ExpectedWSTranscript([..., Sender.Server("hi")]))
    with raises(AssertionError):
        transcripts.assert_requested_with(ExpectedWSTranscript([..., Sender.Server("ho")]))
    transcripts.assert_requested_once_with(ExpectedWSTranscript([..., Sender.Server("hi")]))
    with raises(AssertionError):
        transcripts.assert_requested_once_with(ExpectedWSTranscript([..., Sender.Server("ho")]))
    transcripts.assert_any_request(ExpectedWSTranscript([..., Sender.Server("hi")]))
    with raises(AssertionError):
        transcripts.assert_any_request(ExpectedWSTranscript([..., Sender.Server("ho")]))
