#!/bin/bash
# Development environment setup script

echo "🔧 Setting up development environment..."

# Install pre-commit
echo "📦 Installing pre-commit..."
pip install pre-commit

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to check current state
echo "🔍 Running initial checks..."
pre-commit run --all-files || true

echo "✅ Development environment setup complete!"
echo ""
echo "Pre-commit hooks will now run automatically before each commit."
echo "To run manually: pre-commit run --all-files"
echo ""
echo "Available linters:"
echo "  - Black (code formatting)"
echo "  - isort (import sorting)"
echo "  - Flake8 (style guide enforcement)"
echo "  - MyPy (type checking)"
echo "  - yamllint (YAML validation)"
echo "  - Safety (security vulnerabilities)"