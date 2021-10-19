from contextlib import contextmanager
from logging import getLogger, Filter
from typing import Dict, TypeVar, Mapping, AbstractSet, Iterable

_missing = object()
K = TypeVar('K')
V = TypeVar('V')


class AtLeast(Dict[K, V]):
    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k, v in self.items():
            other_v = other.get(k, _missing)
            if other_v != v:
                return False
        return True

    def __ne__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k, v in self.items():
            other_v = other.get(k, _missing)
            if other_v != v:
                return True
        return False

    def __str__(self):
        if not self:
            return '{**_}'
        return '{' + ', '.join(f'{k!r}: {v!r}' for k, v in self.items()) + ', **_}'

    def __repr__(self):
        return f'AtLeast({super().__repr__()})'


class AtLeastMulti(Dict[K, AbstractSet[V]]):
    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k, v in self.items():
            other_v = other.get(k, _missing)
            if other_v is _missing or not isinstance(other_v, Iterable) or not (v <= frozenset(other_v)):
                return NotImplemented
        return True

    def __ne__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k, v in self.items():
            other_v = other.get(k, _missing)
            if other_v is _missing or not isinstance(other_v, Iterable) or not (frozenset(v) <= frozenset(other_v)):
                return True
        return False

    def __str__(self):
        if not self:
            return '{**_}'
        return ('{'
                + ', '.join(f'{k!r}: '
                            + ('{' + ', '.join(repr(e) for e in v) + ', *_}' if v else '{*_}')
                            for k, v in self.items())
                + ', **_}')

    def __repr__(self):
        return f'AtLeastMulti({super().__repr__()})'


class WhyNot(str):
    @classmethod
    def is_ne(cls, field: str, expected, got):
        return cls(f'{field} mismatch: expected {expected}, got {got}')

    def __bool__(self):
        return False


class MuteFilter(Filter):
    def filter(self, record) -> bool:
        return False


@contextmanager
def mute_uvicorn_log():
    logger = getLogger('uvicorn.error')
    filter_ = MuteFilter()
    logger.addFilter(filter_)
    yield
    logger.removeFilter(filter_)
