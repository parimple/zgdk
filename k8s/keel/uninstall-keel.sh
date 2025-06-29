#!/bin/bash
set -e

echo "Uninstalling Keel..."

# Remove Keel annotations from ZGDK deployment
echo "Removing Keel annotations from ZGDK deployment..."
kubectl annotate deployment zgdk-discord-bot -n zgdk \
  keel.sh/policy- \
  keel.sh/trigger- \
  keel.sh/pollSchedule- \
  --overwrite || true

# Remove pod template annotations
kubectl patch deployment zgdk-discord-bot -n zgdk --type=json -p='[
  {"op": "remove", "path": "/spec/template/metadata/annotations/keel.sh~1policy"},
  {"op": "remove", "path": "/spec/template/metadata/annotations/keel.sh~1trigger"}
]' || true

# Delete Keel deployment and resources
echo "Deleting Keel resources..."
kubectl delete -f keel-deployment.yaml || true
kubectl delete -f namespace.yaml || true

echo "Keel uninstallation complete!"