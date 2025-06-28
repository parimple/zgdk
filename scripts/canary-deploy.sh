#!/bin/bash
# Minimal canary deployment script

NEW_SHA=$1
AGENT_TYPE=${2:-faq}  # Default to FAQ agent

echo "🚀 Starting canary deployment for $AGENT_TYPE agent with SHA: $NEW_SHA"

# Update 1 replica to new version
kubectl patch deployment support-agents-$AGENT_TYPE-agent -n zgdk \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"agent","image":"zgdk/support-agents:'$NEW_SHA'"}]}}}}'

# Wait for rollout
kubectl rollout status deployment/support-agents-$AGENT_TYPE-agent -n zgdk

# Check metrics (simplified)
sleep 30
ERROR_COUNT=$(kubectl logs -l component=$AGENT_TYPE-agent -n zgdk --since=30s | grep -c ERROR || echo 0)

if [ $ERROR_COUNT -gt 5 ]; then
  echo "❌ Too many errors ($ERROR_COUNT), rolling back..."
  kubectl rollout undo deployment/support-agents-$AGENT_TYPE-agent -n zgdk
  exit 1
fi

echo "✅ Canary healthy, proceeding with full rollout"
# ArgoCD will handle the rest via sync