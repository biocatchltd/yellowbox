from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Pattern, List, Iterable, Iterator, Collection

import re

from flask import Request

from yellowbox.extras.webserver.util import WhyNot, SequenceView

try:
    import orjson as json_
except ImportError:
    try:
        import ujson as json_
    except ImportError:
        import json as json_

from igraph import Graph
from typing import Optional, Dict, Any, Union, TypeVar, Mapping, Callable, Tuple, Sequence

_missing = object()
K = TypeVar('K')
V = TypeVar('V')


class AtLeast(Dict[K, V]):
    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k, v in self.items():
            other_v = other.get(k, _missing)
            if other_v is _missing or other_v != v:
                return False
        return True

    def __str__(self):
        if not self:
            return '{**_}'
        return '{' + ', '.join(f'{k!r}: {v!r}' for k, v in self.items()) + ', **_}'

    def __repr__(self):
        return f'AtLeast({super().__repr__()})'


class ExpectedRequest:
    def __init__(self, headers: Optional[Dict[str, Union[Sequence[str]], str]] = None,
                 path: Optional[Union[str, Pattern]] = None,
                 path_args: Optional[Dict[str, Any]] = None,
                 query_args: Optional[Dict[str, Union[Sequence[str]], str]] = None,
                 body: Optional[bytes, Callable[[bytes], bool], Tuple[Callable[[bytes], Any]], Any] = None,
                 text: Optional[str] = None, json: Any = _missing):
        self.headers = dict(headers)
        for k, v in self.headers.items():
            if isinstance(v, str):
                self.headers[k] = (v,)
        if isinstance(path, str):
            self.path_pattern = re.compile(re.escape(path))
        else:
            self.path_pattern = path
        self.path_args = path_args
        self.query_args = dict(query_args)
        for k, v in self.query_args.items():
            if isinstance(v, str):
                self.query_args[k] = (v,)

        if (
                (body is not None)
                + (text is not None)
                + (json is not _missing)
        ) >= 2:
            raise ValueError('only one of content, text, json must be set')

        self.content_decode: Optional[Callable[[bytes], Any]]
        self.decoded_expected: Optional[Any]
        if isinstance(body, tuple):
            self.body_decode, self.data = body
        elif body is not None:
            self.body_decode = lambda x: x
            self.data = body
        elif text is not None:
            self.body_decode = lambda x: x.decode()
            self.data = text
        elif json is not _missing:
            self.body_decode = lambda x: json_.loads(x.decode())
            self.data = json
        else:
            self.body_decode = self.data = None

    def match(self, request: Request) -> Union[bool, WhyNot]:
        if self.headers is not None:
            headers = {}
            for k, v in request.headers:  # flask headers are wierd
                headers.setdefault(k, []).append(v)
            if self.headers != headers:
                return WhyNot.is_ne('header', self.headers, headers)

        if (self.path_pattern is not None
                and self.path_pattern.fullmatch(request.path) is None):
            return WhyNot.is_ne('path', self.path_pattern.pattern, request.path)

        if (self.path_args is not None
                and self.path_args != request.view_args):
            return WhyNot.is_ne('path_params', self.path_args, request.view_args)

        if self.query_args is not None:
            query_args = dict(request.args.lists())
            if self.query_args != query_args:
                return WhyNot.is_ne('query', self.query_args, query_args)

        if self.body_decode is not None:
            body = self.body_decode(request.data)
            if self.data != body:
                return WhyNot.is_ne('body', self.data, body)

        return True

    def __str__(self):
        args = {}
        if self.headers is not None:
            args['headers'] = self.headers
        if self.path_pattern is not None:
            args['path'] = self.path_pattern
        if self.path_args is not None:
            args['path_args'] = self.path_args
        if self.query_args is not None:
            args['query_args'] = self.query_args
        if self.body_decode is not None:
            args['body'] = self.data

        return 'ExpectedResult(' + ', '.join(f'{k}={v!r}' for (k, v) in args.items()) + ')'


@dataclass
class ExistingRequest:
    headers: Dict[str, List[str]]
    path: str
    path_args: Dict[str, Any]
    query_args: Dict[str, Sequence[str]]
    content: bytes

    @classmethod
    def from_request(cls, request: Request):
        headers = {}
        for k, v in request.headers:  # flask headers are wierd
            headers.setdefault(k, []).append(v)

        query_args = dict(request.args.lists())

        return cls(
            headers,
            request.path,
            request.view_args,
            query_args,
            request.data
        )


class CapturedRequests(List[Request]):
    @property
    def summary(self):
        return [ExistingRequest.from_request(request) for request in self]

    def _find_requests_subsequence(self, expected_requests: Collection[ExpectedRequest], any_prefix: bool,
                                   any_postfix: bool):
        requests = iter(enumerate(self))
        passed: List[Tuple[ExistingRequest, Union[ExpectedRequest, WhyNot]]] = []
        for i, expected in enumerate(expected_requests):
            failure_reasons: List[Tuple[ExistingRequest, WhyNot]] = []
            for j, request in requests:
                if not any_postfix and i == len(expected_requests) - 1 and j != len(self) - 1:
                    # if we don't allow postfix, and we're at the last expected, and we're not at the last found
                    # request, don't even bother matching.
                    match = WhyNot('skipped because the last requests must match')
                else:
                    match = expected.match(request)

                if match:
                    passed.append((ExistingRequest.from_request(request), expected))
                    break
                elif not (i or any_prefix):  # if this is the first expected item, and any_prefix is disabled
                    raise AssertionError(f'expected first request {expected}, {match}')
                failure_reasons.append((ExistingRequest.from_request(request), match))
            else:
                # the request list is exhausted and a match was not found
                if failure_reasons:
                    raise AssertionError(f'expected request {expected}, but no requests matched:'
                                         + ''.join((f'\n\t{req}- did not match previous'
                                                    if not match
                                                    else f'\n\t{req}- matched previous {match}')
                                                   for req, match in passed)
                                         + ''.join(f'\n\t{req}- {whynot}' for req, whynot in failure_reasons))
                else:
                    raise AssertionError(f'expected request {expected}, but no requests found')
            passed.extend(existing for (existing, _) in failure_reasons)

    def _find_requests_sequential(self, expected_requests: Sequence[ExpectedRequest], index: int):
        if index + len(expected_requests) >= len(self):
            raise IndexError
        for expected, request in zip(expected_requests, islice(self, index, None)):
            match = expected.match(request)
            if not match:
                return match
        return True

    def assert_requested(self):
        if not self:
            raise AssertionError('No requests were made')

    def assert_requested_once(self):
        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError('Multiple requests were made:'
                                 + ''.join(f'\n\t{existing}' for existing in self.summary))

    def assert_requested_with(self, expected: Optional[ExpectedRequest] = None, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        match = expected.match(self[-1])
        if not match:
            raise AssertionError(str(match))

    def assert_requested_once_with(self, expected: ExpectedRequest, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError('Multiple requests were made:'
                                 + ''.join(f'\n\t{existing}' for existing in self.summary))
        match = expected.match(self[0])
        if not match:
            raise AssertionError(str(match))

    def assert_any_request(self, expected: ExpectedRequest, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        whynots: List[Tuple[ExistingRequest, WhyNot]] = []
        for req in self:
            match = expected.match(req)
            if match:
                return
            whynots.append((ExistingRequest.from_request(req), match))
        raise AssertionError(f'expected request {expected}, but no requests match:',
                             ''.join(f'\n\t {existing}- {whynot}' for (existing, whynot) in whynots))

    def assert_has_requests_any_order(self, *expected_requests: ExpectedRequest, any_prefix=True, any_postfix=True,
                                      any_infix=False):
        return _assert_has_requests_any_order_inner(self, expected_requests, any_prefix, any_postfix, any_infix)

    def assert_has_requests(self, *expected_requests: ExpectedRequest, any_order: bool = False, any_prefix=True,
                            any_postfix=True, any_infix=False):
        if any_order:
            return self.assert_has_requests_any_order(*expected_requests, any_prefix=any_prefix,
                                                      any_postfix=any_postfix, any_infix=any_infix)


def _assert_has_requests_any_order_inner(requests: Sequence[Request], expected_requests: Sequence[ExpectedRequest],
                                         any_prefix: bool, any_postfix: bool, any_infix: bool):
    if len(requests) < len(expected_requests):
        raise AssertionError(f"expected sequential requests {expected_requests}, but found {requests}")

    if not any_infix:
        # not any_infix means that all the chosen requests must be sequential, we check this be check each potential
        # subsequence until we find a match
        if not any_prefix and not any_postfix:
            if len(expected_requests) != len(requests):
                raise AssertionError(f'expected exactly {len(expected_requests)}, but {len(requests)} found')
        elif not any_prefix:
            # the sequence must match the first X requests
            return _assert_has_requests_any_order_inner(requests[:len(expected_requests)], expected_requests, True,
                                                        True, True)
        elif not any_postfix:
            return _assert_has_requests_any_order_inner(requests[-len(expected_requests):], expected_requests, True,
                                                        True, True)
        else:
            for start_ind in range(0, len(requests) - len(expected_requests) + 1):
                try:
                    return _assert_has_requests_any_order_inner(
                        SequenceView(requests, range(start_ind, start_ind + len(expected_requests))),
                        expected_requests, True, True, True)
                except AssertionError:
                    pass
            raise AssertionError(f"expected sequential requests {expected_requests}, but found {requests}")

    edges = []
    why_nots: Dict[ExpectedRequest, Dict[requests, WhyNot]] = {expected: {} for expected in expected_requests}
    for i, expected in enumerate(expected_requests):
        for j, request in enumerate(requests):
            match = expected.match(request)
            if match:
                edges.append((i, j + len(expected_requests)))
            else:
                why_nots[expected][request] = match
    graph = Graph.Bipartite([0] * len(expected_requests) + [1] * len(requests), edges)
    graph.es['weight'] = 1
    if not any_prefix or not any_postfix:
        max_weight = len(requests) + 1
        # in order to force the matching algorithm to prefer connecting to the first and last requests, we increase the
        # weights connecting there
        for edge in graph.es:
            if ((edge.target == len(expected_requests) and not any_prefix)
                    or (edge.target == len(expected_requests) + len(requests) - 1 and not any_postfix)):
                edge['weight'] = max_weight

    max_matching = graph.maximum_bipartite_matching(weights='weight')
    for i, expected in enumerate(expected_requests):
        if not max_matching.is_matched(i):
            raise AssertionError(f'could not match expected request {expected}:'
                                 + ''.join((f'\n\t{req}- {why_nots[expected][req]}'
                                            if req in why_nots[expected]
                                            else f'\n\t{req}- matched expected request '
                                                 + str(expected_requests[max_matching.match_of(node_index)]))
                                           for node_index, req in enumerate(requests, len(expected_requests))))

    if not any_prefix and not max_matching.is_matched(len(expected_requests)):
        raise AssertionError(f'no match for first request {ExistingRequest.from_request(requests[0])},'
                             f' expected {expected_requests}')

    if not any_postfix and not max_matching.is_matched(len(expected_requests) + len(requests) - 1):
        raise AssertionError(f'no match for last request {ExistingRequest.from_request(requests[-1])},'
                             f' expected {expected_requests}')


def _match_subsequence(requests: Sequence[Request], expected_requests: Sequence[ExpectedRequest], any_prefix: bool,
                       any_postfix: bool, any_infix: bool)
