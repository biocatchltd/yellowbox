import platform
from contextlib import AbstractContextManager, closing, contextmanager, nullcontext
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from typing import Callable, TypeVar

from yaspin import yaspin

_T = TypeVar('_T')
_SPINNER_FAILMSG = "💥 "
_SPINNER_SUCCESSMSG = "✅ "


@contextmanager
def _spinner(text):
    with yaspin(text=text) as spinner:
        try:
            yield
        except Exception:
            spinner.fail(_SPINNER_FAILMSG)
            raise
        spinner.ok(_SPINNER_SUCCESSMSG)


def _get_spinner(real=True) -> Callable[[str], AbstractContextManager]:
    if not real:
        return lambda text: nullcontext()
    return _spinner


def get_free_port():
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        return s.getsockname()[1]


uname = platform.uname().release.lower()

if platform.system() == "Linux" and ('microsoft' not in uname):  # catch WSL
    docker_host_name = '172.17.0.1'
else:
    docker_host_name = 'host.docker.internal'

# if we expose a port in docker, this is where we expect to find it hosted
# this is almost always just localhost
DOCKER_EXPOSE_HOST = '127.0.0.1'
if ('microsoft' in uname) and ('wsl2' in uname):
    # wsl2 exposes ports on the microsoft machine, so we need to target it instead
    with open('/etc/resolv.conf') as resolv:
        for line in resolv:
            if line.startswith("nameserver "):
                DOCKER_EXPOSE_HOST = line[len("nameserver "):].strip()
                print(f"resolved DOCKER_EXPOSE_HOST to be {DOCKER_EXPOSE_HOST}")
                break
        else:
            print(f"could not resolve {DOCKER_EXPOSE_HOST}, using default")
