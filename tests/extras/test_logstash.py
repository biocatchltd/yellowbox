import json
import socket
import weakref
from contextlib import suppress
from time import sleep

import pytest

from yellowbox.extras.logstash import FakeLogstashService


@pytest.fixture
def logstash():
    with FakeLogstashService().start() as ls:
        yield ls


def create_socket(logstash):
    return socket.create_connection((logstash.local_host, logstash.port))


def send_record(logstash, **kwargs):
    s = create_socket(logstash)
    s.sendall(json.dumps(kwargs).encode("utf-8") + b"\n")
    s.close()
    sleep(0.01)  # Wait for LogstashService to process.


def send_records(logstash, *records):
    s = create_socket(logstash)
    data = "\n".join([json.dumps(record) for record in records]) + "\n"
    data = data.encode("utf-8")
    s.sendall(data)
    s.close()
    sleep(0.01)


def test_sanity(logstash):
    send_record(logstash, msg="test")
    assert logstash.records[0] == {"msg": "test"}


def test_multiple_records(logstash):
    send_records(logstash, {"msg": "hello"}, {"msg": "meow"})
    assert logstash.records == [{"msg": "hello"}, {"msg": "meow"}]


def test_multiple_connections(logstash):
    send_record(logstash, msg="test")
    send_record(logstash, msg="test2")
    assert logstash.records == [{"msg": "test"}, {"msg": "test2"}]


def test_half_records(logstash):
    s = create_socket(logstash)
    s.sendall(b'{"ms')
    s.sendall(b'g": "t')
    s.sendall(b'est"}\n{"ms')
    sleep(0.01)
    s.sendall(b'g2": "test2"}\n')
    s.close()
    sleep(0.01)
    assert logstash.records == [{"msg": "test"}, {"msg2": "test2"}]


def test_bad_record(logstash):
    s = create_socket(logstash)
    s.sendall(b"{'sdafasdgsdgs\n")
    sleep(1)

    # Bad socket was closed
    with suppress(BrokenPipeError, ConnectionError):
        sleep(0.1)

    # Server still works
    send_record(logstash, msg="hello")
    sleep(0.1)
    assert logstash.records == [{"msg": "hello"}]


def test_assert_logs(logstash):
    send_record(logstash, level="INFO")

    with pytest.raises(AssertionError):
        logstash.assert_logs("ERROR")

    send_record(logstash, level="ERROR")

    # Doesn't throw an error
    logstash.assert_logs("ERROR")


def test_assert_no_logs(logstash):
    send_record(logstash, level="INFO")

    # Doesn't throw an error
    logstash.assert_no_logs("ERROR")

    send_record(logstash, level="ERROR", message="hello")

    with pytest.raises(AssertionError):
        logstash.assert_no_logs("ERROR")


def test_filter_records(logstash):
    send_records(logstash, {"level": "INFO"}, {"level": "WARNING"}, {"level": "ERROR"})
    assert list(logstash.filter_records("warning")) == [{"level": "WARNING"}, {"level": "ERROR"}]


def test_is_alive():
    logstash = FakeLogstashService()
    assert not logstash.is_alive()
    logstash.start()
    assert logstash.is_alive()
    logstash.stop()
    assert not logstash.is_alive()


def test_garbage_collection():
    """Make sure LogstashService gets collected and has no cyclic references

    Important for cleaning OS resources.
    """
    ls = FakeLogstashService()
    r = weakref.ref(ls)
    del ls
    assert r() is None
