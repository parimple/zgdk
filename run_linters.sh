#!/bin/bash -xe

echo "Linters are running..."

# prettier --write .
isort .
black .
