#!/bin/sh
# run various linters
set -e
echo "running black..."
python -m black .
echo "running ruff..."
python -m ruff .  --fix --show-fixes
