# ZGDK Development Makefile

.PHONY: help format lint test install clean docker-up docker-down

help: ## Show this help message
	@echo "ZGDK Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

format: ## Auto-format code with Black and isort
	@echo "🎨 Formatting Python code with Black..."
	black --line-length=120 .
	@echo "📦 Sorting imports with isort..."
	isort --profile black --line-length=120 .
	@echo "✅ Code formatting complete!"

lint: ## Run all linters
	@echo "🔍 Running linters..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🎨 Black (check only)..."
	black --check --line-length=120 .
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📦 isort (check only)..."
	isort --check-only --profile black --line-length=120 .
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🔍 Flake8..."
	flake8 . --config=.flake8
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🔎 MyPy..."
	mypy . --ignore-missing-imports --no-strict-optional || true
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📋 YAML lint..."
	yamllint -c .yamllint .
	@echo "✅ All linters complete!"

test: ## Run tests
	@echo "🧪 Running tests..."
	pytest tests/ -v

install: ## Install development dependencies
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	pip install pre-commit black isort flake8 mypy yamllint pytest
	pre-commit install
	@echo "✅ Dependencies installed!"

pre-commit: ## Run pre-commit on all files
	@echo "🪝 Running pre-commit hooks..."
	pre-commit run --all-files

clean: ## Clean up cache and temporary files
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	@echo "✅ Cleanup complete!"

docker-up: ## Start Docker containers
	@echo "🚀 Starting Docker containers..."
	docker-compose up -d
	@echo "✅ Containers started!"

docker-down: ## Stop Docker containers
	@echo "🛑 Stopping Docker containers..."
	docker-compose down
	@echo "✅ Containers stopped!"

docker-logs: ## Show Docker logs
	docker-compose logs -f --tail=100

docker-shell: ## Open shell in app container
	docker-compose exec app bash

check-health: ## Check container health status
	@docker-compose ps
	@echo ""
	@echo "Health endpoint status:"
	@curl -s http://localhost:8091/health || echo "Health endpoint not responding"

fix-all: format ## Fix all auto-fixable issues
	@echo "🔧 Fixing all auto-fixable issues..."
	@echo "✅ All fixes applied!"

# Development workflow shortcuts
dev: docker-up docker-logs ## Start development environment

stop: docker-down ## Stop development environment