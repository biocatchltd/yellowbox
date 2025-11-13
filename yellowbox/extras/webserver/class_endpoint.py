from collections.abc import Callable
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, overload

from yellowbox.extras.webserver.endpoints import (
    HTTP_SIDE_EFFECT,
    METHODS,
    WS_SIDE_EFFECT,
    MockHTTPEndpoint,
    MockWSEndpoint,
    http_endpoint,
    ws_endpoint,
)

T = TypeVar("T")


class EndpointTemplate(Generic[T]):
    """
    A template for a generic endpoint. To be created before any instance of a subclass of webserver, but to be added to
     all instances.
    """

    constructor: ClassVar[Callable]

    def __init__(self, *args, side_effect_method, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.side_effect_method = side_effect_method
        update_wrapper(self, side_effect_method)

    def construct(self, instance) -> T:
        if hasattr(self.side_effect_method, "__get__"):
            side_effect = self.side_effect_method.__get__(instance, type(instance))
        else:
            side_effect = self.side_effect_method
        return self.constructor(*self.args, side_effect, **self.kwargs)

    if TYPE_CHECKING:

        def __get__(self, instance, owner) -> T: ...


class HTTPEndpointTemplate(EndpointTemplate[MockHTTPEndpoint]):
    """
    A subclass of EndpointTemplate that is used to create an HTTP endpoint.
    """

    constructor = staticmethod(http_endpoint)  # type: ignore[assignment]


class WSEndpointTemplate(EndpointTemplate[MockWSEndpoint]):
    """
    A subclass of EndpointTemplate that is used to create a websocket endpoint.
    """

    constructor = staticmethod(ws_endpoint)  # type: ignore[assignment]


@overload
def class_http_endpoint(
    methods: METHODS,
    rule_string: str,
    *,
    auto_read_body: bool = True,
    forbid_implicit_head_verb: bool = True,
    name: str | None = None,
) -> Callable[[Any], HTTPEndpointTemplate]: ...


@overload
def class_http_endpoint(
    methods: METHODS,
    rule_string: str,
    side_effect: HTTP_SIDE_EFFECT,
    *,
    auto_read_body: bool = True,
    forbid_implicit_head_verb: bool = True,
    name: str | None = None,
) -> HTTPEndpointTemplate: ...


def class_http_endpoint(methods: METHODS, rule_string: str, side_effect: HTTP_SIDE_EFFECT | None = None, **kwargs):
    """
    Creates an HTTP endpoint template. Declare this as a class variable in your webserver subclass to automatically add
     the endpoint to all instances. Can be used as a decorator.
    Args:
        methods: forwarded to MockHTTPEndpoint
        rule_string: forwarded to MockHTTPEndpoint
        side_effect: forwarded to MockHTTPEndpoint
        **kwargs: forwarded to MockHTTPEndpoint

    Returns:
        A new http endpoint template

    """

    def ret(side_effect_method):
        return HTTPEndpointTemplate(methods, rule_string, side_effect_method=side_effect_method, **kwargs)

    if side_effect is not None:
        return ret(side_effect)
    return ret


@overload
def class_ws_endpoint(
    rule_string: str, *, name: str | None = None, allow_abrupt_disconnect: bool = True
) -> Callable[[Any], WSEndpointTemplate]:
    pass


@overload
def class_ws_endpoint(
    rule_string: str, side_effect: WS_SIDE_EFFECT, *, name: str | None = None, allow_abrupt_disconnect: bool = True
) -> WSEndpointTemplate:
    pass


def class_ws_endpoint(rule_string: str, side_effect: WS_SIDE_EFFECT | None = None, **kwargs):
    """
    Creates a websocket endpoint template. Declare this as a class variable in your webserver subclass to automatically
     add the endpoint to all instances. Can be used as a decorator.
    Args:
        rule_string: forwarded to MockWSEndpoint
        side_effect: forwarded to MockWSEndpoint

    Returns:
        A new websocket endpoint template

    """

    def ret(side_effect_method):
        return WSEndpointTemplate(rule_string, side_effect_method=side_effect_method, **kwargs)

    if side_effect is not None:
        return ret(side_effect)
    return ret
