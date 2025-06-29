# Keel - Automatic Deployment Updates for ZGDK

This directory contains the configuration and scripts to set up Keel for automatic deployment updates of the ZGDK Discord bot.

## What is Keel?

Keel is a lightweight Kubernetes operator that automatically updates deployments when new Docker images are available. It's perfect for K3s on ARM64 as it:
- Has minimal resource requirements (50m CPU, 64Mi memory)
- Supports glob patterns for image tag matching
- Works without external dependencies
- Provides simple polling-based updates

## How it Works

1. Keel polls Docker Hub every minute (configurable)
2. It looks for new images matching the pattern `ppyzel/zgdk:main-*`
3. When a new image is found, it automatically updates the deployment
4. The update triggers a rolling deployment with zero downtime

## Installation

```bash
cd /home/ubuntu/Projects/zgdk/k8s/keel
./install-keel.sh
```

## Verification

Check if Keel is running:
```bash
kubectl get pods -n keel
kubectl logs deployment/keel -n keel
```

Check if annotations are applied:
```bash
kubectl describe deployment zgdk-discord-bot -n zgdk | grep keel
```

## Configuration

The current configuration:
- **Policy**: `glob:main-*` - Matches any image with tag starting with "main-"
- **Trigger**: `poll` - Uses polling instead of webhooks
- **Poll Schedule**: `@every 1m` - Checks for new images every minute

To change the polling interval, edit the annotation:
```bash
kubectl annotate deployment zgdk-discord-bot -n zgdk \
  keel.sh/pollSchedule="@every 5m" \
  --overwrite
```

## Monitoring

Watch Keel logs for update activity:
```bash
kubectl logs -f deployment/keel -n keel | grep -E "(update|zgdk)"
```

## Troubleshooting

If updates aren't working:

1. Check Keel logs for errors:
   ```bash
   kubectl logs deployment/keel -n keel --tail=50
   ```

2. Verify annotations are present:
   ```bash
   kubectl get deployment zgdk-discord-bot -n zgdk -o jsonpath='{.metadata.annotations}' | jq .
   ```

3. Test with a manual image update:
   ```bash
   kubectl set image deployment/zgdk-discord-bot bot=ppyzel/zgdk:main-test -n zgdk
   ```

## Uninstallation

To remove Keel and stop automatic updates:
```bash
./uninstall-keel.sh
```

## Alternative Solutions Considered

1. **ArgoCD** - Too heavy for single-node K3s (requires 1GB+ RAM)
2. **Flux CD** - More complex setup, better for GitOps workflows
3. **CronJob** - Would require custom scripting and state management

Keel was chosen as the best balance of simplicity, resource usage, and functionality.