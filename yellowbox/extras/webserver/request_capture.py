from typing import Optional, Dict, List, Any, Union, TypeVar, Mapping

_missing = object()
K = TypeVar('K')
V = TypeVar('V')


class AtLeast(Dict[K, V]):
    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        for k,v in self.items():
            other_v = other.get(k, _missing)
            if other_v is _missing or other_v != v:
                return False
        return True

class ExpectedRequest:
    def __init__(self, headers: Optional[Dict[str, str]] = None, path_params: Optional[Dict[str, Any]] = None,
                 query_strings: Optional[Dict[str, Union[List[str]], str]] = None,
                 content: Optional[bytes] = None, text: Optional[str] = None, json: Any = _missing,
                 msgpack: Any = _missing):
        self.headers = headers

