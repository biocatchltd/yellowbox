import re

from pytest import mark

from yellowbox.extras.webserver.http_request_capture import RecordedHTTPRequest, ExpectedHTTPRequest
from yellowbox.extras.webserver.util import AtLeast, AtLeastMulti


def test_atleast_str():
    al = AtLeast(a=1, b=2)
    assert str(al) == "{'a': 1, 'b': 2, **_}"
    assert repr(al) == "AtLeast({'a': 1, 'b': 2})"


def test_atleast_str_empty():
    al = AtLeast()
    assert str(al) == "{**_}"
    assert repr(al) == "AtLeast({})"


@mark.parametrize('other', [
    {'a': 1, 'b': 2},
    {'a': 1, 'b': 2, 'c': 7},
    {'a': 1, 'b': 2, 'c': 7, 'd': object()},
])
def test_atleast_eq(other):
    al = AtLeast(a=1, b=2)
    assert al == other
    assert other == al
    assert not al != other
    assert not other != al


@mark.parametrize('other', [
    {},
    {'a': 1},
    {'b': 2, 'c': 7},
    {'a': 11, 'b': 2},
    {'a': 1, 'b': 12},
    None, 1, 2, 'A'
])
def test_atleast_ne(other):
    al = AtLeast(a=1, b=2)
    assert al != other
    assert other != al
    assert not al == other
    assert not other == al


def test_atleastmulti_str():
    al = AtLeastMulti(a={1}, b={2})
    assert str(al) == "{'a': {1, *_}, 'b': {2, *_}, **_}"
    assert repr(al) == "AtLeastMulti({'a': {1}, 'b': {2}})"


def test_atleastMulti_str_empty():
    al = AtLeastMulti()
    assert str(al) == "{**_}"
    assert repr(al) == "AtLeastMulti({})"


@mark.parametrize('other', [
    {'a': {1, 11}, 'b': {2, 22}, 'd': set()},
    {'a': [1, 11, 13], 'b': {2, 22}, 'd': set()},
    {'a': {1, 11, 13}, 'b': {2, 22, 23}, 'd': {None}},
    {'a': {1, 11, 13}, 'b': {2, 22, 23}, 'c': {}, 'd': {None}},
])
def test_atleastmulti_eq(other):
    al = AtLeastMulti(a={1, 11}, b={2, 22}, d=frozenset())
    assert al == other
    assert other == al
    assert not al != other
    assert not other != al


@mark.parametrize('other', [
    {},
    {'a': 1, 'b': 1, 'c': 1},
    {'a': {1, 11}, 'b': {2}, 'd': set()},
    {'a': {1, 11}, 'b': {2, 22}, 'e': 15},
    None, 1, 2, 'A'
])
def test_atleastmulti_ne(other):
    al = AtLeastMulti(a={1, 11}, b={2, 22}, d=frozenset())
    assert al != other
    assert other != al
    assert not al == other
    assert not other == al


def test_alm():
    assert not AtLeastMulti(c={'3'}) != {'a': ['1'], 'b': ['2'], 'c': ['3', '4']}


@mark.parametrize('expected', [
    ExpectedHTTPRequest(),
    ExpectedHTTPRequest(headers=AtLeastMulti(c=['3'])),
    ExpectedHTTPRequest(method='GET'),
    ExpectedHTTPRequest(path='/foo/12/bar'),
    ExpectedHTTPRequest(path=re.compile('/foo/[0-9]+/bar')),
    ExpectedHTTPRequest(path_args=AtLeast(x=12)),
    ExpectedHTTPRequest(query_args=AtLeastMulti(y=['15'])),
    ExpectedHTTPRequest(body=b'15'),
    ExpectedHTTPRequest(text='15'),
    ExpectedHTTPRequest(json=15),
    ExpectedHTTPRequest(content_predicate=(int, 15)),
    ExpectedHTTPRequest(content_predicate=lambda x: x.startswith(b'1')),
])
def test_match_recorded_http_call(expected):
    recorded = RecordedHTTPRequest(
        {'a': ['1'], 'b': ['2'], 'c': ['3', '4']},
        'GET',
        '/foo/12/bar',
        {'x': 12},
        {'y': ['15', '17']},
        b'15'
    )

    assert expected.matches(recorded)


@mark.parametrize('expected', [
    ExpectedHTTPRequest(headers=AtLeastMulti(c=['3', '10'])),
    ExpectedHTTPRequest(method='PUT'),
    ExpectedHTTPRequest(path='/foo/12/bar/'),
    ExpectedHTTPRequest(path=re.compile('/foo/[0-1]+/bar')),
    ExpectedHTTPRequest(path_args=AtLeast(t=12)),
    ExpectedHTTPRequest(query_args=AtLeastMulti(y=['15', '16'])),
    ExpectedHTTPRequest(body=b'25'),
    ExpectedHTTPRequest(text='16'),
    ExpectedHTTPRequest(json=11),
    ExpectedHTTPRequest(content_predicate=(int, 12)),
    ExpectedHTTPRequest(content_predicate=lambda x: x.startswith(b'2')),
])
def test_mismatch_recorded_http_call(expected):
    recorded = RecordedHTTPRequest(
        {'a': ['1'], 'b': ['2'], 'c': ['3', '4']},
        'GET',
        '/foo/12/bar',
        {'x': 12},
        {'y': ['15', '17']},
        b'15'
    )

    assert not expected.matches(recorded)
