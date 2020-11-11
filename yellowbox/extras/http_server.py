import re
from collections import defaultdict
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock
from types import new_class
from typing import Pattern, Callable, Set, DefaultDict

from readerwriterlock import rwlock

from yellowbox.service import YellowService


@dataclass
class RoutedHandler:
    method: str
    name: str
    route: Pattern[str]
    callback: Callable[[BaseHTTPRequestHandler], None]

    def __post_init__(self):
        self.route = re.compile(self.route)  # compile is idempotent


class HttpService(YellowService):
    class RequestRouter(BaseHTTPRequestHandler):
        routes_by_method: DefaultDict[str, Set[RoutedHandler]]
        route_lock: rwlock.RWLockWrite

        @classmethod
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.routes_by_method = defaultdict(set)
            cls.route_lock = rwlock.RWLockWrite()

        @classmethod
        def add_route(cls, handler: RoutedHandler):
            with cls.route_lock.gen_wlock():
                cls.routes_by_method[handler.name].add(handler)

        @classmethod
        def del_route(cls, handler: RoutedHandler):
            with cls.route_lock.gen_wlock():
                cls.routes_by_method[handler.name].remove(handler)

        def _do(self):
            matches = []
            first_slash = self.path.find('/')
            if first_slash == -1:
                # path is blank after host
                route = ''
            else:
                route = self.path[first_slash:]
            with self.route_lock.gen_rlock():
                candidates = self.routes_by_method.get(self.command, ())
                for candidate in candidates:
                    if candidate.route.fullmatch(route):
                        matches.append(candidate)
            if not matches:
                self.send_error(404, 'mock server matched no routes')
            if len(matches) > 1:
                self.send_error(500, 'mock server matched multiple routes: '
                                + ', '.join(m.name for m in matches))
            match, = matches
            match.callback(self)
            self.end_headers()

        def __getattr__(self, item: str):
            if item.startswith('do_'):
                method = item[3:]
                if method in self.routes_by_method:
                    return self._do
            raise AttributeError(item)

    def __init__(self, host='0.0.0.0', port=0):
        self.router_cls = new_class('anonymous-RequestRouter', (self.RequestRouter,))
        self.server = HTTPServer((host, port), self.RequestRouter)
