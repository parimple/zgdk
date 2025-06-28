# Kubernetes Guide for ZGDK

## Architektura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Discord Bot   │     │   AI Agents     │     │  Redis Cache    │
│   (1 replica)   │────▶│  (2-10 replicas)│────▶│   (1 replica)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                                 │
                          ┌──────▼──────┐
                          │  PostgreSQL  │
                          │ StatefulSet  │
                          └─────────────┘
```

## Szybki Start

### 1. Lokalne środowisko (Minikube/Kind)

```bash
# Instalacja Skaffold
curl -Lo skaffold https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64
chmod +x skaffold
sudo mv skaffold /usr/local/bin

# Start lokalnego klastra
minikube start --cpus=4 --memory=8192

# Uruchom w trybie dev z hot reload
make k8s-dev
```

### 2. Deployment do różnych środowisk

```bash
# Development (hot reload, sync plików)
skaffold dev --port-forward

# Staging
skaffold run -p staging

# Production
kubectl apply -k k8s/overlays/production
```

## Skalowanie

### Automatyczne skalowanie AI Agents

```yaml
# HPA automatycznie skaluje agentów AI na podstawie:
# - CPU > 70%
# - Memory > 80%
# Min: 2 repliki, Max: 10 replik
```

### Manualne skalowanie

```bash
# Skaluj AI agentów
make k8s-scale-ai REPLICAS=5

# Sprawdź status
kubectl get hpa -n zgdk
```

## Zarządzanie zasobami

### Resource Quotas per Namespace

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: zgdk-quota
spec:
  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    persistentvolumeclaims: "4"
```

### Monitoring zasobów

```bash
# Pod metrics
kubectl top pods -n zgdk

# Node metrics
kubectl top nodes
```

## Środowisko testowe

### 1. Feature Branch Deployments

```bash
# Każdy branch może mieć własne środowisko
skaffold dev --namespace=zgdk-feature-$(git branch --show-current)
```

### 2. Integration Tests w K8s

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-tests
spec:
  template:
    spec:
      containers:
      - name: test-runner
        image: zgdk/bot:latest
        command: ["pytest", "tests/integration/", "-v"]
      restartPolicy: Never
```

### 3. Smoke Tests

```bash
# Run smoke tests po deploymencie
kubectl apply -f k8s/jobs/smoke-test.yaml
kubectl logs job/smoke-test -f
```

## Best Practices

### 1. Health Checks

```python
# W każdym serwisie
@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/ready")
async def ready():
    # Sprawdź połączenia
    await db.ping()
    await redis.ping()
    return {"status": "ready"}
```

### 2. Graceful Shutdown

```python
async def shutdown():
    # Zakończ aktywne zadania
    await bot.close()
    await db.close()
    await redis.close()
```

### 3. ConfigMaps dla różnych środowisk

```yaml
# Dev: debug logging, hot reload
# Staging: info logging, podobne do prod
# Prod: error logging, optymalizacja
```

## Troubleshooting

```bash
# Logi
kubectl logs -f deployment/zgdk-bot -n zgdk --tail=100

# Debug pod
kubectl exec -it deployment/zgdk-bot -n zgdk -- /bin/bash

# Events
kubectl get events -n zgdk --sort-by='.lastTimestamp'

# Describe problematyczny pod
kubectl describe pod <pod-name> -n zgdk
```

## CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
- name: Build and Deploy
  run: |
    skaffold build --tag=${{ github.sha }}
    kubectl set image deployment/zgdk-bot bot=zgdk/bot:${{ github.sha }}
```