#!/bin/sh
set -e
# run the unittests with branch coverage
poetry run pytest --durations=50 -n auto --dist loadfile --cov-branch --cov=./yellowbox --cov-report=xml --cov-report=html --cov-report=term-missing tests/ "$@"