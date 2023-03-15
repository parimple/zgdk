#!/bin/bash -xe

echo "checks are running..."

echo "running prettier..."
prettier . -c

echo "running black..."
black --check .

echo "running isort..."
isort --recursive --check-only --skip .venv .

echo "running pylint..."
pylint datasources cogs tests ./main.py 

echo "running bandit..."
bandit --recursive cogs datasources ./main.py

echo "running pytest..."
pytest --cov=tests/
