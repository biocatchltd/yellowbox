from time import time

from docker.models.containers import Container

from yellowbox.utils import LoggingIterableAdapter, get_container_ports


class Yellow:
    def __init__(self, container: Container, reload_ttl=0):
        self.container = container
        self.stdout = LoggingIterableAdapter(self.container.logs(stream=True, stdout=True, stderr=False))
        self.stderr = LoggingIterableAdapter(self.container.logs(stream=True, stdout=False, stderr=True))
        self.logs = self.container.logs(stream=True)
        self.reload_timeout = -float('inf')
        self.reload_ttl = reload_ttl

    def reload(self, force=False):
        if force or time() > self.reload_timeout:
            self.container.reload()
            self.reload_timeout = time() + self.reload_ttl

    def is_alive(self, force_reload=False):
        self.reload(force_reload)
        return self.container.status.lower() not in ('exited', 'stopped')

    def kill(self, signal='SIGKILL'):
        self.container.kill(signal)

    def ports(self, force_reload=False):
        self.reload(force_reload)
        return get_container_ports(self.container)



