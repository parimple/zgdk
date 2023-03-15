#!/bin/bash -xe

echo "Linters are running..."

prettier --write .
black .
isort .
