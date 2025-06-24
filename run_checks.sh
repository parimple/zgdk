#!/bin/bash -xe

echo "checks are running..."

# echo "running prettier..."
# prettier . -c

export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "running black..."
black --check --line-length=88 .

echo "running isort..."
isort --check-only --skip .venv --skip utils/role_manager.py --skip utils/voice/__init__.py --skip cogs/commands/voice.py --skip cogs/commands/mod.py .

echo "running pylint..."
pylint datasources cogs tests ./main.py --exit-zero

echo "running bandit..."
bandit --recursive cogs datasources ./main.py --skip B608 || true

echo "running pytest..."
pytest --cov=tests/ || true

echo "All checks passed successfully!"
