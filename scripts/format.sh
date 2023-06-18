#!/bin/sh
# run various linters
set -e
echo "running black..."
python -m black .
echo "sorting import with ruff..."
python -m ruff . --select I,F401 --fix --show-fixes