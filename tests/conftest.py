from functools import wraps
from typing import List, Tuple

from docker.models.containers import Container
from pytest import fixture

from tests.util import unique_name_generator
from yellowbox.containers import create_and_pull as _create_and_pull, is_removed


@fixture
def sqlalchemy_version():
    """Provide the installed SQLAlchemy version for tests that need to install it in containers"""
    import sqlalchemy  # noqa: PLC0415

    return sqlalchemy.__version__


@fixture
def create_and_pull():
    """A wrapper around yellowbox's create_and_pull, to ensure that all created containers are removed"""
    created: List[Tuple[Container, bool]] = []

    @wraps(_create_and_pull)
    def ret(*args, remove="auto", **kwargs):
        container = _create_and_pull(*args, **kwargs)
        if remove:
            created.append((container, remove is True))
        return container

    yield ret
    for c, force in created:
        if is_removed(c):
            continue
        if not force and c.status not in ("created", "removing", "paused") and c.wait(timeout=1)["StatusCode"] != 0:
            continue
        c.remove(force=True, v=True)


image_suffix = unique_name_generator()


@fixture
def make_unique_image_name():
    def ret(prefix: str | None) -> str | None:
        if prefix is None:
            return None
        return f"{prefix}{image_suffix()}"

    return ret


# we use this to pass a unique argument to the image build test to ensure that each image we build has a unique sha,
#  ensuring that even anonymous images are uniquely identifiable.
image_arg = fixture(unique_name_generator(), scope="session")
