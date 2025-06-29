#!/bin/bash

echo "=== Image Updater Monitor ==="
echo ""

# Show CronJob status
echo "CronJob Status:"
kubectl get cronjob zgdk-image-updater -n image-updater
echo ""

# Show recent jobs
echo "Recent Jobs (last 5):"
kubectl get jobs -n image-updater --sort-by=.metadata.creationTimestamp | tail -6
echo ""

# Show current deployment image
echo "Current Deployment Image:"
kubectl get deployment zgdk-discord-bot -n zgdk -o jsonpath='{.spec.template.spec.containers[0].image}'
echo -e "\n"

# Show last job logs if available
LAST_POD=$(kubectl get pods -n image-updater --sort-by=.metadata.creationTimestamp -o name | tail -1)
if [ ! -z "$LAST_POD" ]; then
  echo -e "\nLast Job Logs:"
  kubectl logs -n image-updater $LAST_POD --tail=20
fi