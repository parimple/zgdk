#!/bin/bash
set -e

echo "Installing Keel for automatic deployment updates..."

# Create namespace
echo "Creating Keel namespace..."
kubectl apply -f namespace.yaml

# Deploy Keel
echo "Deploying Keel..."
kubectl apply -f keel-deployment.yaml

# Wait for Keel to be ready
echo "Waiting for Keel to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/keel -n keel

# Patch the ZGDK deployment with Keel annotations
echo "Adding Keel annotations to ZGDK deployment..."
kubectl annotate deployment zgdk-discord-bot -n zgdk \
  keel.sh/policy="glob:main-*" \
  keel.sh/trigger="poll" \
  keel.sh/pollSchedule="@every 1m" \
  --overwrite

# Also add annotations to the pod template
kubectl patch deployment zgdk-discord-bot -n zgdk --patch '
spec:
  template:
    metadata:
      annotations:
        keel.sh/policy: "glob:main-*"
        keel.sh/trigger: "poll"
'

echo "Keel installation complete!"
echo ""
echo "Keel will now:"
echo "- Poll Docker Hub every 1 minute for new images"
echo "- Look for images matching pattern: ppyzel/zgdk:main-*"
echo "- Automatically update the deployment when new images are found"
echo ""
echo "To check Keel logs:"
echo "kubectl logs -f deployment/keel -n keel"
echo ""
echo "To check current annotations:"
echo "kubectl describe deployment zgdk-discord-bot -n zgdk | grep keel"