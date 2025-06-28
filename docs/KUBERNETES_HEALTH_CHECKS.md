# Kubernetes Health Checks for ZGDK Bot

## Overview

The ZGDK Discord bot implements Kubernetes health check probes to ensure proper monitoring and automatic recovery in production environments.

## Health Check Endpoints

The bot exposes three health check endpoints on port 8091:

### 1. Liveness Probe (`/health`)
- **Purpose**: Checks if the bot process is alive and responsive
- **Returns**: 200 OK if the bot object exists
- **Kubernetes Action**: Restarts pod if probe fails

### 2. Readiness Probe (`/ready`)
- **Purpose**: Checks if the bot is ready to serve traffic
- **Checks**:
  - Bot is connected to Discord (`bot.is_ready()`)
  - Bot has at least one guild connected
  - Database connection is working
- **Returns**: 200 OK if all checks pass
- **Kubernetes Action**: Removes pod from service endpoints if probe fails

### 3. Startup Probe (`/startup`)
- **Purpose**: Provides time for bot initialization during startup
- **Returns**: 200 OK if bot initialization has started
- **Kubernetes Action**: Allows longer startup time before liveness/readiness probes begin

## Configuration in Helm

The health checks are configured in the Helm chart with the following settings:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8091
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8091
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  successThreshold: 1
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /startup
    port: 8091
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 30
```

## Testing Health Checks

### Local Testing (Docker)
```bash
# Check health
curl http://localhost:8091/health

# Check readiness
curl http://localhost:8091/ready

# Check startup
curl http://localhost:8091/startup
```

### Kubernetes Testing
```bash
# Get pod status
kubectl get pods -l app=zgdk,component=discord-bot

# Describe pod to see probe status
kubectl describe pod -l app=zgdk,component=discord-bot

# Check probe endpoints from within cluster
kubectl exec -it <pod-name> -- curl http://localhost:8091/health
```

## Monitoring

The health check server logs all probe requests and failures. Monitor these logs to understand bot health:

```bash
# View health check logs
kubectl logs -l app=zgdk,component=discord-bot | grep "Health check"
```

## Common Issues

1. **Bot not ready**: Usually means Discord connection is not established
2. **Database error**: Check PostgreSQL connection and credentials
3. **No guilds connected**: Bot may not be invited to any Discord servers

## Implementation Details

The health check server is implemented using `aiohttp` and runs on a separate port (8091) to avoid conflicts with other services. It's started during bot initialization and stopped gracefully during shutdown.