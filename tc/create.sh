#!/bin/bash

towncrier create $(git rev-parse --abbrev-ref HEAD).$1.md "${@:2}"