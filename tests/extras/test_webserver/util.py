from starlette.datastructures import QueryParams
from starlette.status import WS_1000_NORMAL_CLOSURE, WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocket
from websocket import WebSocket as WSClient


def assert_ws_closed(ws_client: WSClient, code: int = 1000):
    resp_opcode, msg = ws_client.recv_data()
    assert resp_opcode == 8
    assert msg == code.to_bytes(2, 'big')


async def do_some_math(ws: WebSocket):
    await ws.accept()
    query_args = QueryParams(ws.scope["query_string"])
    if 'mod' in query_args:
        mod = int(query_args['mod'])
    else:
        mod = None

    v = ws.scope['path_params']['a']
    while True:
        if mod:
            v %= mod
        await ws.send_json(v)
        operation = await ws.receive_json()
        action = operation.get('op')
        if not action:
            return WS_1008_POLICY_VIOLATION
        if action == 'done':
            return WS_1000_NORMAL_CLOSURE
        operand = operation.get('value')
        if operand is None:
            return WS_1008_POLICY_VIOLATION
        if action == 'add':
            v += operand
            continue
        if action == 'mul':
            v *= operand
            continue
