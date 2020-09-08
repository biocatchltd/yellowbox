#!/bin/sh
# run the unittests with branch coverage
poetry run pytest -n auto --dist loadfile --cov-branch --cov=./yellowbox --cov-report=xml tests/
