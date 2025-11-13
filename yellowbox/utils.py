import os
import platform
from collections.abc import Callable
from contextlib import AbstractContextManager, closing, contextmanager, nullcontext
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket

from yaspin import yaspin

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
        s.bind(("", 0))
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        return s.getsockname()[1]


uname = platform.uname().release.lower()

if platform.system() == "Linux" and ("microsoft" not in uname):  # catch WSL
    docker_host_name = "172.17.0.1"
else:
    docker_host_name = "host.docker.internal"

# if we expose a port in docker, this is where we expect to find it hosted
# this is almost always just localhost
# you can set the value here to some value with the YELLOWBOX_DOCKER_EXPOSE_HOST env-var
# DO NOT manually change this const, instead call update_docker_expose_host
DOCKER_EXPOSE_HOST = ""


def update_docker_expose_host(value: str | None):
    """
    update the global docker expose host, attempting to infer from the environment

    Args:
        value: if provided, will use this value instead of inferring a host

    Notes:
        This function is called once when yellowbox is imported with a value of the env var
        YELLOWBOX_DOCKER_EXPOSE_HOST

    """
    global DOCKER_EXPOSE_HOST  # noqa: PLW0603

    if value is None:
        value = "127.0.0.1"

    DOCKER_EXPOSE_HOST = value


update_docker_expose_host(os.getenv("YELLOWBOX_DOCKER_EXPOSE_HOST"))
