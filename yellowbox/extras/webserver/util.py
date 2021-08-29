from abc import abstractmethod
from typing import TypeVar, Sequence, _T_co, overload, Union, Optional


class WhyNot(str):
    @classmethod
    def is_ne(cls, field: str, expected, got):
        return cls(f'{field} mismatch: expected {expected}, got {got}')

    def __bool__(self):
        return False


T = TypeVar('T')


class SequenceView(Sequence[T]):
    def __init__(self, seq: Sequence[T], indices: Optional[range] = None):
        if indices is None:
            indices = range(0, len(seq))
        self.seq = seq
        self.indices = indices

    @overload
    def __getitem__(self, i: int) -> T:
        ...

    @overload
    def __getitem__(self, s: slice) -> Sequence[T]:
        ...

    def __getitem__(self, i: Union[int, slice]) -> T:
        if isinstance(i, slice):
            return SequenceView(self.seq, self.indices[i])
        return self.seq[self.indices[i]]

    def __iter__(self):
        for ind in self.indices:
            yield self.seq[ind]

    def __len__(self):
        return len(self.indices)
