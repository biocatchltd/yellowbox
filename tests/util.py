import random
from typing import Callable


def _random_name(length=16) -> str:
    return ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=length))


def unique_name_generator(length=16) -> Callable[..., str]:
    seen_names = set()

    def gen():
        while True:
            name = _random_name(length)
            if name not in seen_names:
                seen_names.add(name)
                return name

    return gen
