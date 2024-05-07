#!/bin/sh
# checks that a version is ready to be released
set -e

if ls newsfragments/*.md 2> /dev/null; then
    echo "Unbuilt newsfragments exist, exiting" && exit 1
fi

CL_VERSION=$(awk '/^## \[(.+)\]|[0-9.]+/ {print gensub(/(\[(.+)\]|([0-9.]+)).*$/, "\\2\\3", "g", $2); exit}' CHANGELOG.md)
if [ -z "$CL_VERSION" ]; then
    echo "Could not find version in CHANGELOG.md" && exit 1
fi

TOML_VERSION=$(poetry version | cut -d' ' -f2)

if [ "$CL_VERSION" != "$TOML_VERSION" ]; then
    echo "Version mismatch between CHANGELOG.md and pyproject.toml ($CL_VERSION vs $TOML_VERSION)" && exit 1
fi