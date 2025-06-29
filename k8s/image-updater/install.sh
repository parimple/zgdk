#!/bin/bash
set -e

echo "Installing Image Updater for automatic deployment updates..."

# Create namespace
echo "Creating image-updater namespace..."
kubectl apply -f namespace.yaml

# Deploy Image Updater
echo "Deploying Image Updater CronJob..."
kubectl apply -f image-updater.yaml

echo "Image Updater installation complete!"
echo ""
echo "The Image Updater will:"
echo "- Check Docker Hub every 5 minutes for new images"
echo "- Look for images matching pattern: ppyzel/zgdk:main-*"
echo "- Automatically update the deployment when new images are found"
echo ""
echo "To check CronJob status:"
echo "kubectl get cronjob -n image-updater"
echo ""
echo "To check recent job runs:"
echo "kubectl get jobs -n image-updater"
echo ""
echo "To manually trigger an update:"
echo "kubectl create job --from=cronjob/zgdk-image-updater manual-update-$(date +%s) -n image-updater"
echo ""
echo "To view logs from the last job:"
echo 'kubectl logs -n image-updater $(kubectl get pods -n image-updater --sort-by=.metadata.creationTimestamp -o name | tail -1)'