from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Collection, Dict, Iterable, List, Mapping, Optional, Pattern, Sequence, Tuple, Union, overload

from starlette.requests import HTTPConnection
from starlette.websockets import WebSocket

from yellowbox.extras.webserver.request_capture import ScopeExpectation
from yellowbox.extras.webserver.util import MismatchReason, reason_is_ne


class WebSocketRecorder(WebSocket):
    """
    A subclass of starlette.Websocket that records the conversation in a transcript
    messages are parsed as per https://asgi.readthedocs.io/en/latest/specs/www.html#websocket
    """

    def __init__(self, scope, receive, send, sinks: Sequence[RecordedWSTranscripts]):
        """
        Args:
            scope: forwarded to Websocket
            receive: forwarded to Websocket
            send: forwarded to Websocket
            sinks: a list of transcripts to add the transcript to
        """
        super().__init__(scope, receive, send)
        self.transcript: RecordedWSTranscript = RecordedWSTranscript.from_connection(self)
        for sink in sinks:
            sink.append(self.transcript)

    async def receive(self):
        message = await super().receive()
        message_type = message.get('type')
        if message_type == "websocket.receive":
            # by asgi uvicorn implementation (def asgi_receive), a message will always contain exactly one of
            #  'text' or 'data'
            data = message.get('text')
            if data is None:
                data = message.get('bytes')
            self.transcript.append(RecordedWSMessage(data, Sender.Client))
        elif message_type == "websocket.disconnect":
            self.transcript.close = (Sender.Client, message.get('code', 1000))
        return message

    async def send(self, message):
        message_type = message["type"]
        if message_type == "websocket.accept":
            self.transcript.accepted = True
        elif message_type == "websocket.close":
            self.transcript.close = (Sender.Server, message.get('code', 1000))
        elif message_type == "websocket.send":
            # by asgi uvicorn implementation (def asgi_receive), a message will always contain exactly one of
            #  'text' or 'data'
            data = message.get('text')
            if data is None:
                data = message.get('bytes')
            self.transcript.append(RecordedWSMessage(data, Sender.Server))
        await super().send(message)


class RecorderEndpoint:
    """
    An entrypoint app that records websocket conversations
    Args:
        function: the function to call the endpoint with
        sinks: a list of transcripts that the record should be added to
    """

    def __init__(self, function, sinks: Sequence[RecordedWSTranscripts]):
        self.function = function
        self.sinks = sinks

    async def __call__(self, scope, receive, send):
        ws = WebSocketRecorder(scope, receive, send, sinks=self.sinks)
        return await self.function(ws)


class Sender(Enum):
    """
    A sender that can send messages in a transcript. A sender can be called to create an expected message.

    Examples:
        >>> import re
        ... expected_message = Sender.Server(re.compile('[a-z][a-z][0-9]'))
        ... message = RecordedWSMessage('tk1', Sender.Server)
        ... assert expected_message.matches(message)
    """
    Server = auto()
    Client = auto()

    def __call__(self, data: Union[Pattern[str], Pattern[bytes], str, bytes, ellipsis]) \
            -> ExpectedWSMessage:  # noqa: F821
        """
        Create an expected message, originating from this caller
        Args:
            data: the expected data of the message. Can be either a bytes or string for an exact match, a compiled
             pattern for a full match, or ellipsis to match any data.
        """
        return ExpectedWSMessage(data, self)


@dataclass
class RecordedWSMessage:
    """
    A recorded websocket message, with a sender and value sent
    """
    data: Union[bytes, str]
    sender: Sender

    def __repr__(self):
        return f'RecordedWSMessage({self.data!r}, Sender.{self.sender.name})'


class RecordedWSTranscript(List[RecordedWSMessage]):
    """
    A transcript of a single websocket connection
    """

    def __init__(self, arg: Iterable[RecordedWSMessage], headers: Dict[bytes, List[bytes]], path: str,
                 path_params: Dict[str, Any], query_params: Dict[str, List[str]]):
        """
        Args:
            arg: forwarded to super (List)
            headers: the headers of the connection
            path: the path of the connection request
            path_params: the path params of the connection request, as specified by the route's starlette rule string
            query_params: the query params of the connection request
        """
        super().__init__(arg)
        self.headers = headers
        self.path = path
        self.path_params = path_params
        self.query_params = query_params
        self.accepted: bool = False
        """Whether the message was ever accepted by the server"""
        self.close: Optional[Tuple[Sender, int]] = None
        """The sender who closed the connection, along with the close code"""

    @classmethod
    def from_connection(cls, connection: HTTPConnection):
        """
        Create an empty transcript from a new http connection
        Args:
            connection: the http connection to use
        """
        headers: Dict[bytes, List[bytes]] = {}
        for h_k, h_v in connection.headers.raw:
            h_lst = headers.get(h_k)
            if h_lst is None:
                headers[h_k] = [h_v]
            else:
                h_lst.append(h_v)
        path = connection.url.path
        path_params = connection.path_params
        query_params: Dict[str, List[str]] = {}
        for q_k, q_v in connection.query_params.multi_items():
            q_lst = query_params.get(q_k)
            if q_lst is None:
                query_params[q_k] = [q_v]
            else:
                q_lst.append(q_v)
        return cls((), headers, path, path_params, query_params)


class ExpectedWSMessage:
    """
    A single expected message in a websockets connection
    """

    def __init__(self, data: Union[Pattern[str], Pattern[bytes], str, bytes, ellipsis], sender: Sender):  # noqa: F821
        """
        Args:
            data: the expected data. Can be either a bytes or string for an exact match, a compiled pattern for a full
             match, or ellipsis to match any data.
            sender: The sender to expect the message from.
        """
        self.data = data
        self.sender = sender

    def matches(self, message: RecordedWSMessage) -> Union[bool, MismatchReason]:
        """
        Checks whether a recorded message matches the expectation
        Args:
            message: the recorded message

        Returns:
            True if the message matches, or a mismatch reason otherwise.
        """
        if self.sender != message.sender:
            return MismatchReason(reason_is_ne('sender', self.sender, message.sender))

        if self.data is ...:
            return True
        elif isinstance(self.data, Pattern):
            try:
                match = self.data.fullmatch(message.data)  # type:ignore[arg-type]
            except TypeError:  # this would happen when we try to use byte patterns on strs or vice-versa
                match = None
            if not match:
                return MismatchReason(f'expected data to match pattern {self.data.pattern!r}, got {message.data!r}')
            return True
        else:
            if self.data != message.data:
                return MismatchReason(reason_is_ne('data', self.data, message.data))
        return True

    def __str__(self):
        return f'{self.sender.name}({self.data})'


class ExpectedWSTranscript(ScopeExpectation):
    """
    An expected websocket transcript
    """

    def __init__(self, messages: Sequence[Union[ellipsis, ExpectedWSMessage]] = (...,),  # noqa: F821
                 headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 path: Optional[Union[str, Pattern[str]]] = None, path_params: Optional[Mapping[str, Any]] = None,
                 path_params_submap: Optional[Mapping[str, Any]] = None,
                 query_params: Optional[Mapping[str, Collection[str]]] = None,
                 query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                 close: Optional[Tuple[Sender, int]] = None, accepted: Optional[bool] = True):
        """
        Args:
            messages: the expected messages in the transcript, can begin or end ellipsis to signify that any
                number of messages can precede or follow the messages to match.
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
            close: If specified, must be a tuple of sender and an integer. Expects the transcript to be closed by that
             sender with that code.
            accepted: If specified, will only match transcripts of accepted connections (if True) or rejected
             connections (if False)
        """
        super().__init__(headers, headers_submap, path, path_params, path_params_submap, query_params,
                         query_params_submap)
        if messages and messages[0] is ...:
            messages = messages[1:]
            self.any_start = True
        else:
            self.any_start = False

        if messages and messages[-1] is ...:
            messages = messages[:-1]
            self.any_end = True
        else:
            self.any_end = False

        if any(m is ... for m in messages):
            raise TypeError('ExpectedWSTranscript can only contain ellipsis at the start and at the end')

        self.expected_messages: Tuple[ExpectedWSMessage] = messages  # type:ignore[assignment]
        self.accepted = accepted
        self.close = close

    def matches(self, recorded: RecordedWSTranscript):
        """
        Checks whether a recorded transcript matches the expectation
        Args:
            recorded: the recorded transcript

        Returns:
            True if the transcript matches, or a mismatch reason otherwise.
        """
        if recorded.close is None:
            raise RuntimeError('the transcript is not yet done')

        reasons = list(self.scope_mismatch_reasons(recorded))

        if self.close is not None and recorded.close != self.close:
            reasons.append(reason_is_ne('close_code', self.close, recorded.close))
        if self.accepted is not None and recorded.accepted != self.accepted:
            reasons.append(reason_is_ne('accepted', self.accepted, recorded.accepted))

        if not self.any_start and not self.any_end and len(recorded) != len(self.expected_messages):
            reasons.append(f'expected exactly {len(self.expected_messages)} messages, found {len(recorded)}')
        if len(recorded) < len(self.expected_messages):
            reasons.append(f'expected at least {len(self.expected_messages)} messages, found only {len(recorded)}')
        if reasons:
            return MismatchReason(', '.join(reasons))
        # in order to account for any_start, any_end, we check every subsequence of the recorded transcript
        # we store a list of candidate indices for the subsequence start
        if not self.any_start:
            # the case of (not any_start and not any_end) is covered by the first condition
            indices: Iterable[int] = (0,)
        elif not self.any_end:
            indices = (len(recorded) - len(self.expected_messages),)
        else:
            indices = range(0, len(recorded) - len(self.expected_messages) + 1)

        whynots = []
        for start_index in indices:
            for i, expected_message in enumerate(self.expected_messages):
                rec = recorded[start_index + i]
                match = expected_message.matches(rec)
                if not match:
                    whynots.append(f'{rec} did not match {expected_message}: {match}')
                    break
            else:
                return True

        return MismatchReason('could not find expected calls' + ''.join('\n\t' + wn for wn in whynots))


class RecordedWSTranscripts(List[RecordedWSTranscript]):
    """
    A list of recorded WS transcripts, in the order that the connections began
    """

    def assert_not_requested(self):
        """
        asserts that no connections were recorded.
        """
        if self:
            raise AssertionError(f'{len(self)} requests were made')

    def assert_requested(self):
        """
        asserts that at least one transcript was recorded.
        """
        if not self:
            raise AssertionError('No requests were made')

    def assert_requested_once(self):
        """
        asserts that exactly one transcript was recorded.
        """
        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError(f'{len(self)} requests were made')

    @overload
    def assert_requested_with(self, expected: ExpectedWSTranscript):
        ...

    @overload
    def assert_requested_with(self, *, messages: Sequence[Union[ellipsis, ExpectedWSMessage]] = (...,),  # noqa: F821
                              headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                              headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                              path: Optional[Union[str, Pattern[str]]] = None,
                              path_params: Optional[Mapping[str, Any]] = None,
                              path_params_submap: Optional[Mapping[str, Any]] = None,
                              query_params: Optional[Mapping[str, Collection[str]]] = None,
                              query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                              close: Optional[Tuple[Sender, int]] = None, accepted: Optional[bool] = True):
        ...

    def assert_requested_with(self, expected: Optional[ExpectedWSTranscript] = None, **kwargs):
        """
        Asserts that the latest transcript recorded matches an expected transcript
        Args:
            expected: an expected transcript.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedWSTranscript.
        """
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedWSTranscript(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        match = expected.matches(self[-1])
        if not match:
            raise AssertionError(str(match))

    @overload
    def assert_requested_once_with(self, expected: ExpectedWSTranscript):
        ...

    @overload
    def assert_requested_once_with(self, *,
                                   messages: Sequence[Union[ellipsis, ExpectedWSMessage]] = (...,),  # noqa: F821
                                   headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                                   headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                                   path: Optional[Union[str, Pattern[str]]] = None,
                                   path_params: Optional[Mapping[str, Any]] = None,
                                   path_params_submap: Optional[Mapping[str, Any]] = None,
                                   query_params: Optional[Mapping[str, Collection[str]]] = None,
                                   query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                                   close: Optional[Tuple[Sender, int]] = None, accepted: Optional[bool] = True):
        ...

    def assert_requested_once_with(self, expected: Optional[ExpectedWSTranscript] = None, **kwargs):
        """
        Asserts that there is only one transcript, and that it matches an expected transcript
        Args:
            expected: an expected transcript.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedWSTranscript.
        """
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedWSTranscript(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError(f'{len(self)} requests were made')
        match = expected.matches(self[0])
        if not match:
            raise AssertionError(str(match))

    @overload
    def assert_any_request(self, expected: ExpectedWSTranscript):
        ...

    @overload
    def assert_any_request(self, *, messages: Sequence[Union[ellipsis, ExpectedWSMessage]] = (...,),  # noqa: F821
                           headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                           headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                           path: Optional[Union[str, Pattern[str]]] = None,
                           path_params: Optional[Mapping[str, Any]] = None,
                           path_params_submap: Optional[Mapping[str, Any]] = None,
                           query_params: Optional[Mapping[str, Collection[str]]] = None,
                           query_params_submap: Optional[Mapping[str, Collection[str]]] = None,
                           close: Optional[Tuple[Sender, int]] = None, accepted: Optional[bool] = True):
        ...

    def assert_any_request(self, expected: Optional[ExpectedWSTranscript] = None, **kwargs):
        """
        Asserts that the at least one transcript recorded matches an expected transcript
        Args:
            expected: an expected transcript.
            **kwargs: if an expected request is not provided, then a new expected request is constructed by forwarding
             the keyword arguments to the constructor of ExpectedWSTranscript.
        """
        if expected and kwargs:
            raise TypeError('method can be called with either expected or keyword args, but not both')
        if not expected:
            if not kwargs:
                raise TypeError('either expected or keyword args must be provided')
            expected = ExpectedWSTranscript(**kwargs)

        if not self:
            raise AssertionError('No requests were made')
        if any(expected.matches(req) for req in self):
            return
        raise AssertionError('No transcripts match')
