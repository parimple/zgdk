#!/bin/bash -xe

echo "checks are running..."

# echo "running prettier..."
# prettier . -c

export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "running black..."
black --check --line-length=88 .

echo "running isort..."
isort --check-only --skip .venv .

echo "running pylint..."
pylint datasources cogs tests ./main.py 

echo "running bandit..."
bandit --recursive cogs datasources ./main.py

echo "running pytest..."
pytest --cov=tests/
