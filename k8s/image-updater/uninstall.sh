#!/bin/bash
set -e

echo "Uninstalling Image Updater..."

# Delete resources
echo "Deleting Image Updater resources..."
kubectl delete -f image-updater.yaml || true
kubectl delete -f namespace.yaml || true

echo "Image Updater uninstallation complete!"