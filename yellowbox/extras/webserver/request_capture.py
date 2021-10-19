from typing import Optional, Mapping, Union, Collection, Pattern, Any
import re

from yellowbox.extras.webserver.util import WhyNot


class ScopeExpectation:
    def __init__(self, headers: Optional[Mapping[str, Collection[str]]] = None,
                 path: Optional[Union[str, Pattern]] = None,
                 path_args: Optional[Mapping[str, Any]] = None,
                 query_args: Optional[Mapping[str, Collection[str]]] = None):
        self.headers = headers

        if isinstance(path, str):
            self.path_pattern = re.compile(re.escape(path))
        else:
            self.path_pattern = path
        self.path_params = path_args
        self.query_params = query_args

    def matches(self, recorded):
        if self.headers is not None and self.headers != recorded.headers:
            return WhyNot.is_ne('header', self.headers, recorded.headers)

        if (self.path_pattern is not None
                and self.path_pattern.fullmatch(str(recorded.path)) is None):
            return WhyNot.is_ne('path', self.path_pattern.pattern, recorded.path)

        if self.path_params is not None and self.path_params != recorded.path_params:
            return WhyNot.is_ne('path_params', self.path_params, recorded.path_params)

        if self.query_params is not None and self.query_params != recorded.query_params:
            return WhyNot.is_ne('query_params', self.query_params, recorded.query_params)

        return True
