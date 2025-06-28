#!/bin/bash
# Rollback Support Agents deployment

RELEASE_NAME=${RELEASE_NAME:-support-agents}
NAMESPACE=${NAMESPACE:-zgdk}

echo "🔙 Rolling back Support Agents..."

# Step 1: Get current revision
CURRENT_REV=$(argocd app get $RELEASE_NAME -o json | grep -Po '"revision":\s*"\K[^"]+' | head -1)
echo "Current revision: $CURRENT_REV"

# Step 2: Rollback ArgoCD
echo "Rolling back ArgoCD application..."
argocd app rollback $RELEASE_NAME || {
    echo "❌ ArgoCD rollback failed, trying manual rollback..."
    
    # Manual rollback
    for agent in intake faq complaint escalation; do
        echo "Rolling back $agent agent..."
        kubectl rollout undo deployment/$RELEASE_NAME-$agent-agent -n $NAMESPACE
    done
}

# Step 3: Wait for rollback
echo "⏳ Waiting for rollback to complete..."
for agent in intake faq complaint escalation; do
    kubectl rollout status deployment/$RELEASE_NAME-$agent-agent -n $NAMESPACE --timeout=5m
done

# Step 4: Verify
echo "✅ Rollback complete!"
kubectl get pods -n $NAMESPACE -l app=$RELEASE_NAME