import re
from collections import Counter
from typing import Any, Collection, Iterable, Iterator, Mapping, Optional, Pattern, Tuple, TypeVar, Union

from yellowbox.extras.webserver.util import MismatchReason, reason_is_ne

T = TypeVar('T')

_missing = object()
K = TypeVar('K')
V = TypeVar('V')


def _is_submap_of(submap: Mapping[K, V], supermap: Mapping[K, V]):
    """
    checks whether a map is a submap of another map
    Args:
        submap: the submap to check
        supermap: the supermap to check

    Returns:
        True if the condition exists, or a MismatchReason otherwise.

    Notes:
        Mapping A is a submap of Mapping B iff every pair in A also exists in B
    """
    for k, v in submap.items():
        other_v = supermap.get(k, _missing)  # type:ignore[arg-type]
        if other_v is _missing:
            return MismatchReason(f'expected key {k}, none found')
        if other_v != v:
            return MismatchReason(f'expected key {k} to have value {v}, got {other_v}')
    return True


def _is_submultimap_of(submultimap: Mapping[K, Collection[V]], supermultimap: Mapping[K, Collection[V]]):
    """
    checks whether a map is a submultimap of another map
    Args:
        submultimap: the submultimap to check
        supermultimap: the supermultimap to check

    Returns:
        True if the condition exists, or a MismatchReason otherwise.

    Notes:
        Mapping A is a submap of Mapping B iff for every key k in A, Counter(B[k]) >= Counter(A[k])
    """
    for k, v in submultimap.items():
        other_v = supermultimap.get(k, _missing)
        if other_v is _missing:
            return MismatchReason(f'expected key {k}, none found')
        if not isinstance(other_v, Iterable):
            return MismatchReason(f'expected key {k} to be in iterable {other_v}')
        diff = Counter(other_v)
        diff.subtract(Counter(v))
        missing_value = next((k for (k, v) in diff.items() if v < 0), _missing)
        if missing_value is not _missing:
            expected = sum(i == missing_value for i in v)
            return MismatchReason(f'expected value {missing_value} to appear {expected} times in key {k}'
                                  f', got {other_v}')
    return True


def _to_expected_map(name: str, exact: Optional[T], submap: Optional[T]) -> Optional[Tuple[T, bool]]:
    """
    A utility function to convert two parameters one representing an exact-match expectation and one a submap
     expectation, into a single value.

    Args:
        name: the name of the exact match parameter
        exact: the exact-match parameter value
        submap: the subset-match parameter value

    Returns:
        a 2-tuple, containing the expected value, and whether the value is an expected submap, or None if no parameters
         were provided
    """
    if exact is not None:
        if submap is not None:
            raise TypeError(f'at most one of "{name}" and "{name}_submap" can be provided')
        return exact, False
    if submap is not None:
        return submap, True
    return None


def _matches_expected_map(name: str, expected: Optional[Tuple[Mapping[K, V], bool]], recorded: Mapping[K, V]) \
        -> Optional[str]:
    """
    Matches a map against the return value of _to_expected_map
    Args:
        name: the name of the field being matched
        expected: the expected value, as returned by _to_expected_map
        recorded: the recorded value to match

    Returns:
        True if the condition matches, or a MismatchReason otherwise.
    """
    if expected is None:
        return None
    expected_value, is_subset = expected
    if is_subset:
        submap_match = _is_submap_of(expected_value, recorded)
        if not submap_match:
            return f'{name} mismatch: {submap_match}'
    else:
        if expected_value != recorded:
            return reason_is_ne(name, expected_value, recorded)
    return None


def _matches_expected_multimap(name: str, expected: Optional[Tuple[Mapping[K, Collection[V]], bool]],
                               recorded: Mapping[K, Collection[V]]) -> Optional[str]:
    """
    Matches a multimap against the return value of _to_expected_map
    Args:
        name: the name of the field being matched
        expected: the expected value, as returned by _to_expected_map
        recorded: the recorded value to match

    Returns:
        None if the condition matches, or a string describing the reason otherwise.
    """
    if expected is None:
        return None
    expected_value, is_subset = expected
    if is_subset:
        submap_match = _is_submultimap_of(expected_value, recorded)
        if not submap_match:
            return f'{name} mismatch: {submap_match}'
    else:
        if expected_value != recorded:
            return reason_is_ne(name, expected_value, recorded)
    return None


def _repr_map(name: str, expected: Optional[Tuple[T, bool]]):
    """
    A utility function to convert the return value of _to_expected_map back to the provided parameters needed to
     construct it.
    Args:
        name: the name of the exact-match parameter
        expected: the return value of _to_expected_map for these parameters

    Returns:
        a mapping of the parameters that would result in this expectation if passed to the constructor
    """
    if expected is None:
        return {}
    expected_value, is_subset = expected
    if is_subset:
        return {f'{name}_submap': expected_value}
    else:
        return {name: expected_value}


class ScopeExpectation:
    """
    A utility mixin class representing an expected http scope, common to both HTTP and websockets.
    """

    def __init__(self, headers: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 headers_submap: Optional[Mapping[bytes, Collection[bytes]]] = None,
                 path: Optional[Union[str, Pattern[str]]] = None, path_params: Optional[Mapping[str, Any]] = None,
                 path_params_submap: Optional[Mapping[str, Any]] = None,
                 query_params: Optional[Mapping[str, Collection[str]]] = None,
                 query_params_submap: Optional[Mapping[str, Collection[str]]] = None, ):
        self.headers = _to_expected_map('headers', headers, headers_submap)
        if isinstance(path, str):
            self.path_pattern = re.compile(re.escape(path))
        else:
            self.path_pattern = path
        self.path_params = _to_expected_map('path_params', path_params, path_params_submap)
        self.query_params = _to_expected_map('query_params', query_params, query_params_submap)

    def scope_mismatch_reasons(self, recorded) -> Iterator[str]:
        header_match = _matches_expected_multimap('header', self.headers, recorded.headers)
        if header_match:
            yield header_match

        if (self.path_pattern is not None
                and self.path_pattern.fullmatch(str(recorded.path)) is None):
            yield reason_is_ne('path', self.path_pattern.pattern, recorded.path)

        path_params_match = _matches_expected_map('path_params', self.path_params, recorded.path_params)
        if path_params_match:
            yield path_params_match

        query_params_match = _matches_expected_multimap('query_params', self.query_params, recorded.query_params)
        if query_params_match:
            yield query_params_match

    def _repr_map(self):
        """
        Returns: a mapping of the parameters used to create this mixin instance
        """
        args = {
            **_repr_map('headers', self.headers),
            **_repr_map('path_params', self.path_params),
            **_repr_map('query_params', self.query_params),
        }
        if self.path_pattern is not None:
            args['path'] = self.path_pattern
        return args
