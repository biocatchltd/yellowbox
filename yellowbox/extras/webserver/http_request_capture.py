from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Pattern, List, Collection, Optional, Dict, Any, Union, Mapping, Callable, Tuple, Sequence

from igraph import Graph
from starlette.requests import Request

from yellowbox.extras.webserver.request_capture import ScopeExpectation
from yellowbox.extras.webserver.util import WhyNot

try:
    import orjson as json_
except ImportError:
    try:
        import ujson as json_
    except ImportError:
        import json as json_

_missing = object()


class ExpectedHTTPRequest(ScopeExpectation):
    def __init__(self, headers: Optional[Mapping[str, Collection[str]]] = None,
                 path: Optional[Union[str, Pattern]] = None,
                 path_args: Optional[Mapping[str, Any]] = None,
                 query_args: Optional[Mapping[str, Collection[str]]] = None,
                 method: Optional[str] = None,
                 body: Optional[bytes] = None,
                 text: Optional[str] = None, json: Any = _missing,
                 content_predicate: Optional[Union[Callable[[bytes], bool], Tuple[Callable[[bytes], Any], Any]]] = None):
        super().__init__(headers, path, path_args, query_args)

        if method is None:
            self.method = None
        else:
            self.method = method.upper()

        if (
                (body is not None)
                + (text is not None)
                + (json is not _missing)
                + (content_predicate is not None)
        ) >= 2:
            raise ValueError('only one of content, text, json must be set')

        self.body_decode: Optional[Callable[[bytes], Any]]
        self.data: Optional[Any]
        if body is not None:
            self.body_decode = lambda x: x
            self.data = body
        elif text is not None:
            self.body_decode = lambda x: x.decode()
            self.data = text
        elif json is not _missing:
            self.body_decode = lambda x: json_.loads(x.decode())
            self.data = json
        elif isinstance(content_predicate, tuple):
            self.body_decode, self.data = content_predicate
        elif callable(content_predicate):
            self.body_decode = content_predicate
            self.data = True
        else:
            self.body_decode = self.data = None

    def matches(self, recorded: RecordedHTTPRequest) -> Union[bool, WhyNot]:
        scope_match = super().matches(recorded)
        if not scope_match:
            return scope_match

        if self.method and self.method != recorded.method:
            return WhyNot.is_ne('body', self.method, recorded.method)

        if self.body_decode is not None:
            body = self.body_decode(recorded.content)
            if self.data != body:
                return WhyNot.is_ne('body', self.data, body)

        return True

    def __str__(self):
        args = {}
        if self.headers is not None:
            args['headers'] = self.headers
        if self.path_pattern is not None:
            args['path'] = self.path_pattern
        if self.path_params is not None:
            args['path_args'] = self.path_params
        if self.query_params is not None:
            args['query_args'] = self.query_params
        if self.body_decode is not None:
            args['body'] = self.data

        return 'ExpectedResult(' + ', '.join(f'{k}={v!r}' for (k, v) in args.items()) + ')'


@dataclass
class RecordedHTTPRequest:
    headers: Dict[str, List[str]]
    method: str
    path: str
    path_params: Dict[str, Any]
    query_params: Dict[str, Sequence[str]]
    content: bytes

    @classmethod
    async def from_request(cls, request: Request):
        headers = {}
        for k, v in request.headers.items():
            if k not in headers:
                headers[k] = [v]
            else:
                headers[k].append(v)

        query_args = {}
        for k, v in request.query_params.multi_items():
            if k not in query_args:
                query_args[k] = [v]
            else:
                query_args[k].append(v)

        return cls(
            headers,
            request.method,
            request.url.path,
            request.path_params,
            query_args,
            await request.body()
        )


class RecordedHTTPRequests(List[RecordedHTTPRequest]):
    def _find_requests_subsequence(self, expected_requests: Collection[ExpectedHTTPRequest], any_prefix: bool,
                                   any_postfix: bool):
        requests = iter(enumerate(self))
        passed: List[Tuple[RecordedHTTPRequest, Union[ExpectedHTTPRequest, WhyNot]]] = []
        for i, expected in enumerate(expected_requests):
            failure_reasons: List[Tuple[RecordedHTTPRequest, WhyNot]] = []
            for j, request in requests:
                if not any_postfix and i == len(expected_requests) - 1 and j != len(self) - 1:
                    # if we don't allow postfix, and we're at the last expected, and we're not at the last found
                    # request, don't even bother matching.
                    match = WhyNot('skipped because the last requests must match')
                else:
                    match = expected.matches(request)

                if match:
                    passed.append((request, expected))
                    break
                elif not (i or any_prefix):  # if this is the first expected item, and any_prefix is disabled
                    raise AssertionError(f'expected first request {expected}, {match}')
                failure_reasons.append((request, match))
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

    def _find_requests_sequential(self, expected_requests: Sequence[ExpectedHTTPRequest], index: int):
        if index + len(expected_requests) >= len(self):
            raise IndexError
        for expected, request in zip(expected_requests, islice(self, index, None)):
            match = expected.matches(request)
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
                                 + ''.join(f'\n\t{existing}' for existing in self))

    def assert_requested_with(self, expected: Optional[ExpectedHTTPRequest] = None, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedHTTPRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        match = expected.matches(self[-1])
        if not match:
            raise AssertionError(str(match))

    def assert_requested_once_with(self, expected: Optional[ExpectedHTTPRequest] = None, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedHTTPRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError('Multiple requests were made:'
                                 + ''.join(f'\n\t{existing}' for existing in self))
        match = expected.matches(self[0])
        if not match:
            raise AssertionError(str(match))

    def assert_any_request(self, expected: ExpectedHTTPRequest, **kwargs):
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedHTTPRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        whynots: List[Tuple[RecordedHTTPRequest, WhyNot]] = []
        for req in self:
            match = expected.matches(req)
            if match:
                return
            whynots.append((req, match))
        raise AssertionError(f'expected request {expected}, but no requests match:',
                             ''.join(f'\n\t {existing}- {whynot}' for (existing, whynot) in whynots))

    def assert_has_requests_any_order(self, *expected_requests: ExpectedHTTPRequest):
        return _assert_has_requests_any_order_inner(self, expected_requests)

    def assert_has_requests(self, *expected_requests: ExpectedHTTPRequest, any_order: bool = False):
        if any_order:
            return self.assert_has_requests_any_order(*expected_requests)
        return _assert_match_subsequence(self, expected_requests)


def _assert_has_requests_any_order_inner(requests: Sequence[RecordedHTTPRequest],
                                         expected_requests: Sequence[ExpectedHTTPRequest]):
    if len(requests) < len(expected_requests):
        raise AssertionError(f"expected sequential requests {expected_requests}, but found {requests}")

    edges = []
    why_nots: Dict[ExpectedHTTPRequest, Dict[RecordedHTTPRequest, WhyNot]] = {expected: {} for expected in
                                                                              expected_requests}
    for i, expected in enumerate(expected_requests):
        for j, request in enumerate(requests):
            match = expected.matches(request)
            if match:
                edges.append((i, j + len(expected_requests)))
            else:
                why_nots[expected][request] = match
    graph = Graph.Bipartite([0] * len(expected_requests) + [1] * len(requests), edges)

    max_matching = graph.maximum_bipartite_matching(weights='weight')
    for i, expected in enumerate(expected_requests):
        if not max_matching.is_matched(i):
            raise AssertionError(f'could not match expected request {expected}:'
                                 + ''.join((f'\n\t{req}- {why_nots[expected][req]}'
                                            if req in why_nots[expected]
                                            else f'\n\t{req}- matched expected request '
                                                 + str(expected_requests[max_matching.match_of(node_index)]))
                                           for node_index, req in enumerate(requests, len(expected_requests))))


def _assert_match_subsequence(requests: Sequence[RecordedHTTPRequest],
                              expected_requests: Sequence[ExpectedHTTPRequest]):
    if not expected_requests:
        return True
    if len(requests) < len(expected_requests):
        raise AssertionError(f"could not find request to match {expected_requests[0]}")
    # match greedily
    expected_iter = iter(expected_requests)
    try:
        next_expected = next(expected_iter)
    except StopIteration:
        return True
    for request in requests:
        match = next_expected.matches(request)
        if match:
            try:
                next_expected = next(expected_iter)
            except StopIteration:
                return True
    raise AssertionError(f"could not find request to match {next_expected}")
