# 🚀 ZGDK Kubernetes Deployment Guide

## Prerequisites

1. **Kubernetes cluster** z dostępem (kubeconfig skonfigurowany)
2. **kubectl** zainstalowany
3. **helm** zainstalowany (v3+)
4. **Discord Bot Token** z https://discord.com/developers/applications
5. **Guild ID** twojego serwera Discord

## Kroki deploymentu

### 1. Edytuj konfigurację

Otwórz `helm/zgdk/files/config.yml` i podmień:
- `guild_id` - ID twojego serwera Discord
- ID kanałów w sekcji `channels` - znajdź w Discord (Developer Mode)

### 2. Uruchom skrypt deploymentu

```bash
cd /path/to/zgdk
./scripts/deploy-to-k8s.sh
```

Skrypt zapyta o:
- Discord Bot Token (ZAGADKA_TOKEN)
- PostgreSQL hasło
- Gemini API Key (opcjonalne)

### 3. Sprawdź status

```bash
# Zobacz pody
kubectl get pods -n zgdk

# Sprawdź logi
kubectl logs -n zgdk -l component=discord-bot -f

# Sprawdź health
kubectl describe pod -n zgdk -l component=discord-bot
```

### 4. Zainstaluj ArgoCD (opcjonalne)

Jeśli masz ArgoCD w klastrze:

```bash
./scripts/argocd-setup.sh
```

## Troubleshooting

### Bot nie startuje
```bash
# Sprawdź logi
kubectl logs -n zgdk -l component=discord-bot --tail=100

# Sprawdź eventy
kubectl get events -n zgdk --sort-by='.lastTimestamp'
```

### Brak połączenia z bazą danych
```bash
# Sprawdź czy PostgreSQL działa
kubectl get pod -n zgdk -l app=postgres

# Sprawdź secret
kubectl get secret postgres-secrets -n zgdk
```

### Health check failuje
```bash
# Test ręczny
kubectl exec -it -n zgdk deployment/zgdk-discord-bot -- curl http://localhost:8091/health
```

## Ważne adresy

- **Bot w klastrze**: `zgdk-discord-bot.zgdk.svc.cluster.local`
- **PostgreSQL**: `postgres-service.zgdk.svc.cluster.local:5432`
- **Redis**: `redis-service.zgdk.svc.cluster.local:6379`

## Aktualizacja

Po każdym push do main, GitHub Actions:
1. Buduje nowy obraz Docker
2. Pushuje do Docker Hub
3. Aktualizuje tag w `helm/zgdk/values.yaml`

Aby zaktualizować deployment:
```bash
# Pobierz najnowsze zmiany
git pull

# Zaktualizuj Helm release
helm upgrade zgdk ./helm/zgdk -n zgdk
```

Lub z ArgoCD - automatyczna synchronizacja!