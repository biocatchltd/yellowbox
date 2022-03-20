#!/bin/sh
# run the unittests with branch coverage
poetry run coverage run --include="yellowbox/**" -m pytest -n auto --dist loadfile tests/ "$@"
coverage html
coverage report -m
coverage xml