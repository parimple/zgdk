# Image Updater - Automatic Deployment Updates for ZGDK

This directory contains a lightweight CronJob-based solution for automatic deployment updates of the ZGDK Discord bot on K3s ARM64.

## Overview

The Image Updater is a simple Kubernetes CronJob that:
- Runs every 5 minutes
- Checks Docker Hub for new images matching `ppyzel/zgdk:main-*`
- Compares with the currently deployed image
- Updates the deployment if a new image is found
- Waits for the rollout to complete

## Architecture

- **CronJob**: Schedules the update checks
- **ConfigMap**: Contains the update script
- **ServiceAccount**: Provides necessary permissions
- **Alpine/K8s Image**: Lightweight container with kubectl pre-installed

## Installation

```bash
cd /home/ubuntu/Projects/zgdk/k8s/image-updater
./install.sh
```

## Verification

Check if the CronJob is created:
```bash
kubectl get cronjob -n image-updater
```

Check recent job runs:
```bash
kubectl get jobs -n image-updater
```

View logs from the most recent job:
```bash
kubectl logs -n image-updater $(kubectl get pods -n image-updater --sort-by=.metadata.creationTimestamp -o name | tail -1)
```

## Manual Update Trigger

To manually trigger an update check:
```bash
kubectl create job --from=cronjob/zgdk-image-updater manual-update-$(date +%s) -n image-updater
```

Then watch the logs:
```bash
kubectl logs -f job/manual-update-* -n image-updater
```

## Configuration

The update behavior is configured in the ConfigMap within `image-updater.yaml`:

- **NAMESPACE**: Target namespace (zgdk)
- **DEPLOYMENT**: Target deployment name (zgdk-discord-bot)
- **CONTAINER**: Container name within the deployment (bot)
- **IMAGE**: Docker Hub image (ppyzel/zgdk)
- **TAG_PATTERN**: Pattern to match for tags (main-)

Schedule is configured in the CronJob spec:
- Default: `*/5 * * * *` (every 5 minutes)

To change the schedule, edit the CronJob:
```bash
kubectl edit cronjob zgdk-image-updater -n image-updater
```

## Monitoring

### Check Job History
```bash
kubectl get jobs -n image-updater --sort-by=.metadata.creationTimestamp
```

### View Success/Failure Count
```bash
kubectl describe cronjob zgdk-image-updater -n image-updater
```

### Set up Alerts (Optional)
You can monitor failed jobs:
```bash
kubectl get jobs -n image-updater -o json | jq '.items[] | select(.status.failed > 0) | .metadata.name'
```

## Resource Usage

The solution is extremely lightweight:
- **CPU**: 50m request, 100m limit
- **Memory**: 64Mi request, 128Mi limit
- **Storage**: None required
- **Network**: Minimal (one API call to Docker Hub)

## Troubleshooting

### Jobs Not Running
```bash
# Check CronJob status
kubectl describe cronjob zgdk-image-updater -n image-updater

# Check for suspended state
kubectl get cronjob zgdk-image-updater -n image-updater -o jsonpath='{.spec.suspend}'
```

### Update Failures
```bash
# Check job logs
kubectl logs -n image-updater job/zgdk-image-updater-<timestamp>

# Common issues:
# - Network connectivity to Docker Hub
# - Insufficient permissions (check ServiceAccount)
# - Deployment rollout failures
```

### Manual Testing
Test the update script directly:
```bash
kubectl run test-updater --rm -it --image=alpine/k8s:1.29.0 \
  --serviceaccount=image-updater -n image-updater \
  --command -- /bin/sh
# Then run the update commands manually
```

## Security Considerations

- ServiceAccount has minimal permissions (only deployment updates)
- No credentials stored (uses public Docker Hub API)
- Read-only access to deployments
- Restricted to specific namespace

## Uninstallation

To remove the Image Updater:
```bash
./uninstall.sh
```

## Why This Solution?

1. **Lightweight**: Uses minimal resources, perfect for K3s
2. **ARM64 Compatible**: Uses Alpine-based image that works on ARM
3. **Simple**: No complex operators or controllers
4. **Reliable**: Built on Kubernetes native primitives
5. **Observable**: Easy to monitor through standard Kubernetes tools

## Alternative Solutions Attempted

- **Keel**: No official ARM64 support
- **ArgoCD**: Too resource-heavy for single-node K3s
- **Flux**: Overly complex for simple image updates