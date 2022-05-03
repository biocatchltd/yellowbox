from functools import wraps
from typing import List, Tuple

from docker.models.containers import Container
from pytest import fixture

from yellowbox.containers import create_and_pull as _create_and_pull, is_removed


@fixture
def create_and_pull():
    """A wrapper around yellowbox's create_and_pull, to ensure that all created containers are removed
    """
    created: List[Tuple[Container, bool]] = []

    @wraps(_create_and_pull)
    def ret(*args, remove='auto', **kwargs):
        container = _create_and_pull(*args, **kwargs)
        if remove:
            created.append((container, remove is True))
        return container

    yield ret
    for c, force in created:
        if is_removed(c):
            continue
        if not force \
                and c.status not in ('created', 'removing', 'paused')\
                and c.wait(timeout=1)['StatusCode'] != 0:
            continue
        c.remove(force=True, v=True)
