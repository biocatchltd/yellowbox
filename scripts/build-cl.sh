#!/bin/sh
set -e
towncrier build --version "$(poetry version | cut -d' ' -f2)" "$@"