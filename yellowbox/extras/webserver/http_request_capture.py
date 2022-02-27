from __future__ import annotations

from dataclasses import dataclass
from json import loads as json_loads
from typing import Any, Callable, Collection, List, Mapping, Optional, Pattern, Sequence, Tuple, Union, overload

from starlette.requests import Request

from yellowbox.extras.webserver.request_capture import ScopeExpectation
from yellowbox.extras.webserver.util import MismatchReason, reason_is_ne

_missing = object()


class ExpectedHTTPRequest(ScopeExpectation):
    """
    An expected HTTP request
    """

    def __init__(self, headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 path: Optional[Union[str, Pattern[str]]] = None, path_params: Optional[Mapping[str, Any]] = None,
                 path_params_submap: Optional[Mapping[str, Any]] = None,
                 query_params: Optional[Mapping[str, Collection[str]]] = None,
                 query_params_submap: Optional[Mapping[str, Collection[str]]] = None, method: Optional[str] = None,
                 body: Optional[bytes] = None, text: Optional[str] = None, json: Any = _missing,
                 content_predicate: Optional[Union[Callable[[bytes], bool], Tuple[Callable[[bytes], Any], Any]]]
                 = None):
        """
        Args:
            headers: If specified, expects the request to have these headers exactly
            headers_submap: If specified expects the request to have at least the headers specified
            path: If specified, expected the request url (after the host) to either be equal to this (in case of string)
             or to fully match the regex pattern provided
            path_params: If specified, expects the request to have exactly these path parameters, as provided by the
             starlette request
            path_params_submap: if specified, expects the result to have at least theses path parameters, as provided
             by the starlette request
            query_params: If specified, expects the request to have these query arguments exactly
            query_params_submap: If specified, expects the request to have at least these query arguments
            method: If specified, expects the request to have that HTTP method (case-insensitive)
            body: If specified, expects the request to have that exact byte content. Cannot be used alongside other
             content-testing parameters
            text: If specified, expects the request to have that exact text content (using strict utf-8 decoding).
             Cannot be used alongside other content-testing parameters
            json: If specified, expects the JSON-decoded content of the request to be equal to the specified value.
             Cannot be used alongside other content-testing parameters
            content_predicate: If specified, must be either a callable that accepts a bytes object, or a tuple of a
             callable that accepts a bytes object and another value, and expects the return value of the callable with
             the content of the request to evaluate to either True or the second element of the tuple, if one is
             provided. Cannot be used alongside other content-testing parameters
        """
        super().__init__(headers, headers_submap, path, path_params, path_params_submap, query_params,
                         query_params_submap)

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
            self.body_decode = lambda x: json_loads(x.decode())
            self.data = json
        elif isinstance(content_predicate, tuple):
            self.body_decode, self.data = content_predicate
        elif callable(content_predicate):
            self.body_decode = content_predicate
            self.data = True
        else:
            self.body_decode = self.data = None

    def matches(self, recorded: RecordedHTTPRequest) -> Union[bool, MismatchReason]:
        """
        Test if an http request meets the expectations of self
        Args:
            recorded: a recorded http request

        Returns:
            True if the request matches, or a MismatchReason object with the reason why otherwise.
        """
        reasons = list(self.scope_mismatch_reasons(recorded))

        if self.method and self.method != recorded.method:
            reasons.append(reason_is_ne('body', self.method, recorded.method))

        if self.body_decode is not None:
            try:
                body = self.body_decode(recorded.content)
            except Exception as e:
                reasons.append(f'failed to parse content: {e!r}')
            else:
                if self.data != body:
                    reasons.append(reason_is_ne('content', self.data, body))

        if reasons:
            return MismatchReason(', '.join(reasons))
        return True

    def __repr__(self):
        args = self._repr_map()
        if self.method is not None:
            args['method'] = self.method
        if self.body_decode is not None:
            args['content'] = self.data

        return 'ExpectedHTTPRequest(' + ', '.join(f'{k}={v!r}' for (k, v) in args.items()) + ')'


@dataclass
class RecordedHTTPRequest:
    """
    A recorded HTTP request, received by a starlette application.
    """
    headers: Mapping[str, Sequence[str]]
    method: str
    path: str
    path_params: Mapping[str, Any]
    query_params: Mapping[str, Sequence[str]]
    content: bytes

    @classmethod
    async def from_request(cls, request: Request):
        """
        Create a new recorded request from a starlette request.
        Args:
            request: the active starlette request

        Returns:
            the recorded recorded request

        Notes:
            this method waits for and reads the request body
        """
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
    """
    A list of recorded HTTP requests, in the order they were received
    """

    def assert_not_requested(self):
        """
        asserts that no requests were recorded.
        """
        if self:
            raise AssertionError(f'{len(self)} requests, latest: {self[-1]}')

    def assert_requested(self):
        """
        asserts that at least one request was recorded.
        """
        if not self:
            raise AssertionError('No requests were made')

    def assert_requested_once(self):
        """
        asserts that exactly one request was recorded.
        """
        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError('Multiple requests were made:'
                                 + ''.join(f'\n\t{existing}' for existing in self))

    @overload
    def assert_requested_with(self, expected: ExpectedHTTPRequest):
        ...

    @overload
    def assert_requested_with(self, *, headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                              headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                              path: Optional[Union[str, Pattern[str]]] = None,
                              path_params: Optional[Mapping[str, Any]] = None,
                              path_params_submap: Optional[Mapping[str, Any]] = None,
                              query_params: Optional[Mapping[str, Collection[str]]] = None,
                              query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                              method: Optional[str] = None, body: Optional[bytes] = None,
                              text: Optional[str] = None, json: Any = _missing,
                              content_predicate:
                              Optional[Union[Callable[[bytes], bool], Tuple[Callable[[bytes], Any], Any]]] = None):
        ...

    def assert_requested_with(self, expected: Optional[ExpectedHTTPRequest] = None, **kwargs):
        """
        Asserts that the latest request recorded matches an expected request
        Args:
            expected: an expected request.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedHTTPRequest.
        """
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

    @overload
    def assert_requested_once_with(self, expected: ExpectedHTTPRequest):
        ...

    @overload
    def assert_requested_once_with(self, *, headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                                   headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                                   path: Optional[Union[str, Pattern[str]]] = None,
                                   path_params: Optional[Mapping[str, Any]] = None,
                                   path_params_submap: Optional[Mapping[str, Any]] = None,
                                   query_params: Optional[Mapping[str, Collection[str]]] = None,
                                   query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                                   method: Optional[str] = None, body: Optional[bytes] = None,
                                   text: Optional[str] = None, json: Any = _missing,
                                   content_predicate:
                                   Optional[Union[Callable[[bytes], bool], Tuple[Callable[[bytes], Any], Any]]] = None):
        ...

    def assert_requested_once_with(self, expected: Optional[ExpectedHTTPRequest] = None, **kwargs):
        """
        Asserts that there is only one request, and that it matches an expected request
        Args:
            expected: an expected request.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedHTTPRequest.
        """
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

    @overload
    def assert_any_request(self, expected: ExpectedHTTPRequest):
        ...

    @overload
    def assert_any_request(self, *, headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                           headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                           path: Optional[Union[str, Pattern[str]]] = None,
                           path_params: Optional[Mapping[str, Any]] = None,
                           path_params_submap: Optional[Mapping[str, Any]] = None,
                           query_params: Optional[Mapping[str, Collection[str]]] = None,
                           query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                           method: Optional[str] = None, body: Optional[bytes] = None,
                           text: Optional[str] = None, json: Any = _missing,
                           content_predicate:
                           Optional[Union[Callable[[bytes], bool], Tuple[Callable[[bytes], Any], Any]]] = None):
        ...

    def assert_any_request(self, expected: Optional[ExpectedHTTPRequest] = None, **kwargs):
        """
        Asserts that at least one request recorded matches an expected request
        Args:
            expected: an expected request.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedHTTPRequest.
        """
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedHTTPRequest(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        whynots: List[Tuple[RecordedHTTPRequest, MismatchReason]] = []
        for req in self:
            match = expected.matches(req)
            if match:
                return
            assert isinstance(match, MismatchReason)
            whynots.append((req, match))
        raise AssertionError(f'expected request {expected}, but no requests match:',
                             ''.join(f'\n\t {existing}- {whynot}' for (existing, whynot) in whynots))

    def assert_has_requests(self, *expected_requests: ExpectedHTTPRequest):
        """
        Asserts that all of the expected requests exclusively match a one of the recorded requests, in sequential order.
        Args:
            *expected_requests: the expected requests.
        Notes:
            The matched requests must be sequential relative to the expected requests, but they needn't be contiguous.
             This means that if requests A,B are expected, then the recorded request sequence A,C,B matches it.
        """
        if not expected_requests:
            raise TypeError('at least one expected request must be provided')

        if len(self) < len(expected_requests):
            raise AssertionError(f"could not find request to match {expected_requests[0]}")
        # match greedily
        expected_iter = iter(expected_requests)
        next_expected = next(expected_iter)
        for request in self:
            match = next_expected.matches(request)
            if match:
                try:
                    next_expected = next(expected_iter)
                except StopIteration:
                    return True
        raise AssertionError(f"could not find request to match {next_expected}")
