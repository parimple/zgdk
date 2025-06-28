.PHONY: dev prod test reload logs shell clean

# Development mode with hot reload
dev:
	docker-compose -f docker-compose.yml -f docker/docker-compose.dev.yml up

# Production mode
prod:
	docker-compose up -d

# Quick test without Docker
test-local:
	python -m pytest tests/ -v

# Test specific command
test-cmd:
	@echo "Usage: make test-cmd CMD=command_name"
	python scripts/testing/test_command.py $(CMD)

# Reload all cogs (via MCP)
reload:
	curl -X POST http://localhost:8089/execute -H "Content-Type: application/json" -d '{"command": "reload"}'

# View logs
logs:
	docker-compose logs -f app --tail=100

# Shell into container
shell:
	docker-compose exec app /bin/bash

# Clean everything
clean:
	docker-compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Quick restart (tylko app, nie DB)
restart:
	docker-compose restart app

# Install dev dependencies
install-dev:
	pip install watchdog pytest-asyncio httpx

# === Kubernetes Commands ===

# Start local k8s development with Skaffold
k8s-dev:
	skaffold dev --port-forward

# Deploy to staging
k8s-staging:
	skaffold run -p staging

# Deploy to production
k8s-prod:
	kubectl apply -k k8s/overlays/production

# Scale AI agents
k8s-scale-ai:
	kubectl scale deployment ai-agents --replicas=$(REPLICAS)

# View logs
k8s-logs:
	kubectl logs -f deployment/zgdk-bot -n zgdk-dev

# Get pod status
k8s-status:
	kubectl get pods -n zgdk-dev

# Port forward to local
k8s-forward:
	kubectl port-forward deployment/zgdk-bot 8089:8089 -n zgdk-dev

# Run integration tests in k8s
k8s-test:
	kubectl apply -f k8s/jobs/test-job.yaml
	kubectl wait --for=condition=complete job/integration-tests -n zgdk-dev --timeout=300s

# Clean up k8s resources
k8s-clean:
	kubectl delete namespace zgdk-dev