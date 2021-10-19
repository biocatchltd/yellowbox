from __future__ import annotations

from enum import Enum, auto
from starlette.requests import HTTPConnection
from typing import List, Union, Pattern, Tuple, Sequence, Optional, Any, Mapping, Collection

from starlette.websockets import WebSocket

from yellowbox.extras.webserver.request_capture import ScopeExpectation
from yellowbox.extras.webserver.util import WhyNot


class WebSocketRecorder(WebSocket):
    """
    An subclass of websocket that records the conversation
    messages are parsed as per https://asgi.readthedocs.io/en/latest/specs/www.html#websocket
    """

    def __init__(self, scope, receive, send, sinks: Sequence[RecordedWSTranscripts]):
        super().__init__(scope, receive, send)
        self.transcript: RecordedWSTranscript = RecordedWSTranscript(
            connection=self,
        )
        for sink in sinks:
            sink.append(self.transcript)

    async def receive(self):
        message = await super().receive()
        message_type = message.get('type')
        if message_type == "websocket.receive":
            self.transcript.append(RecordedWSMessage(message.get('text') or message.get('bytes'), Sender.Client))
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
            self.transcript.append(RecordedWSMessage(message.get('text') or message.get('bytes'), Sender.Server))
        await super().send(message)


async def recorder_websocket_endpoint(scope, receive, send, *, func, sinks: Sequence[RecordedWSTranscripts]):
    ws = WebSocketRecorder(scope, receive, send, sinks=sinks)
    return await func(ws)


class Sender(Enum):
    Server = auto()
    Client = auto()

    def __call__(self, data: Union[str, bytes]):
        return RecordedWSMessage(data, self)


class RecordedWSMessage:
    def __init__(self, data: Union[bytes, str], sender: Sender):
        self.data = data
        self.sender = sender

    def __repr__(self):
        return f'{self.sender.name}({self.data!r})'

    def __eq__(self, other):
        return isinstance(other, RecordedWSMessage) and self.sender == other.sender and self.data == other.data


class RecordedWSTranscript(List[RecordedWSMessage]):
    def __init__(self, *args, connection: HTTPConnection):
        super().__init__(*args)
        self.headers = {}
        for k, v in connection.headers.raw:
            lst = self.headers.get(k)
            if lst is None:
                self.headers[k] = [v]
            else:
                lst.append(v)
        self.path = connection.url.path
        self.path_params = connection.path_params
        self.query_params = {}
        connection.query_params.multi_items()
        for k, v in connection.query_params.multi_items():
            lst = self.query_params.get(k)
            if lst is None:
                self.query_params[k] = [v]
            else:
                lst.append(v)
        self.accepted: bool = False
        self.close: Optional[Tuple[Sender, int]] = None


class ExpectedWSMessage:
    def __init__(self, data: Union[Pattern[str], Pattern[bytes], str, bytes, type(...)], sender: Sender):
        self.data = data
        self.sender = sender

    def matches(self, message: RecordedWSMessage) -> Union[bool, WhyNot]:
        if self.sender != message.sender:
            return WhyNot.is_ne('sender', self.sender, message.sender)

        if self.data is ...:
            return True
        elif isinstance(self.data, Pattern):
            try:
                match = self.data.fullmatch(message.data)
            except TypeError:  # this would happen when we try to use byte patterns on strs or vice-versa
                match = None
            if not match:
                return WhyNot(f'expected data to match pattern {self.data.pattern}, got {message.data}')
            return True
        else:
            if self.data != message.data:
                return WhyNot.is_ne('data', self.data, message.data)


class ExpectedWSTranscript(ScopeExpectation):
    def __init__(self, *expected_messages: Union[ellipsis, ExpectedWSMessage],
                 close: Optional[Tuple[Sender, int]] = None, accepted: Optional[bool] = True,
                 headers: Optional[Mapping[str, Collection[str]]] = None,
                 path: Optional[Union[str, Pattern]] = None,
                 path_args: Optional[Mapping[str, Any]] = None,
                 query_args: Optional[Mapping[str, Collection[str]]] = None):
        super().__init__(headers, path, path_args, query_args)
        if expected_messages and expected_messages[0] is ...:
            expected_messages = expected_messages[1:]
            self.any_start = True
        else:
            self.any_start = False

        if expected_messages and expected_messages[-1] is ...:
            expected_messages = expected_messages[:-1]
            self.any_end = True
        else:
            self.any_end = False

        if any(m is ... for m in expected_messages):
            raise TypeError('ExpectedWSTranscript can only contain ellipsis at the start and at the end')

        self.expected_messages = expected_messages
        self.accepted = accepted
        self.close = close

    def matches(self, recorded: RecordedWSTranscript):
        scope_match = super().matches(recorded)
        if not scope_match:
            return scope_match

        if recorded.close is None:
            return WhyNot('the transcript is not yet done')
        if self.close is not None and recorded.close != self.close:
            return WhyNot.is_ne('close_code', self.close, recorded.close)
        if self.accepted is not None and recorded.accepted != self.accepted:
            return WhyNot.is_ne('accepted', self.accepted, recorded.accepted)

        if not self.any_start and not self.any_end and len(recorded) != len(self.expected_messages):
            return WhyNot(f'expected exactly {len(self.expected_messages)} messages, found {len(recorded)}')
        if len(recorded) < len(self.expected_messages):
            return WhyNot(f'expected at least {len(self.expected_messages)} messages, found only {len(recorded)}')
        # in order to account for any_start, any_end, we check every subsequence of the recorded transcript
        # we store a list of candidate indices for the subsequence start
        if not self.any_start:
            # the case of (not any_start and not any_end) is covered by the first condition
            indices = (0,)
        elif not self.any_end:
            indices = (len(recorded) - len(self.expected_messages),)
        else:
            indices = range(0, len(recorded) - len(self.expected_messages))

        for start_index in indices:
            for i, expected_message in enumerate(self.expected_messages):
                rec = recorded[start_index + i]
                if not expected_message.matches(rec):
                    break
            else:
                return True

        return WhyNot('could not find expected calls')


class RecordedWSTranscripts(List[RecordedWSTranscript]):
    def assert_requested(self):
        if not self:
            raise AssertionError('No requests were made')

    def assert_requested_once(self):
        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError(f'{len(self)} requests were made')

    def assert_requested_with(self, expected: ExpectedWSTranscript):
        if not self:
            raise AssertionError('No requests were made')
        match = expected.matches(self[-1])
        if not match:
            raise AssertionError(str(match))

    def assert_requested_once_with(self, expected: ExpectedWSTranscript):
        if not self:
            raise AssertionError('No requests were made')
        if len(self) > 1:
            raise AssertionError(f'{len(self)} requests were made')
        match = expected.matches(self[0])
        if not match:
            raise AssertionError(str(match))

    def assert_any_request(self, expected: ExpectedWSTranscript):
        if not self:
            raise AssertionError('No requests were made')
        if any(expected.matches(req) for req in self):
            return
        raise AssertionError(f'No transcripts match')
