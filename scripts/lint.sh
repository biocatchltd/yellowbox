#!/bin/sh
# run various linters
set -e
echo "running ruff..."
python -m ruff check .
python -m ruff .
echo "running mypy..."
python3 -m mypy --show-error-codes yellowbox
