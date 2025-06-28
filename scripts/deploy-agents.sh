#!/bin/bash
# Deploy Support Agents with monitoring

set -e

NAMESPACE=${NAMESPACE:-zgdk}
RELEASE_NAME=${RELEASE_NAME:-support-agents}
ENVIRONMENT=${ENVIRONMENT:-prod}

echo "🚀 Deploying Support Agents to $ENVIRONMENT"

# Step 1: Ensure ArgoCD app exists
echo "📋 Checking ArgoCD application..."
if ! kubectl get application $RELEASE_NAME -n argocd &>/dev/null; then
    echo "Creating ArgoCD application..."
    kubectl apply -f argocd/support-agents-app.yaml
    sleep 5
fi

# Step 2: Sync application
echo "🔄 Syncing ArgoCD application..."
argocd app sync $RELEASE_NAME --prune

# Step 3: Wait for sync
echo "⏳ Waiting for sync to complete..."
argocd app wait $RELEASE_NAME --sync --health --timeout 300

# Step 4: Check deployment status
echo "📊 Checking deployment status..."
kubectl get deployments -n $NAMESPACE -l app=$RELEASE_NAME

# Step 5: Monitor rollout
echo "👀 Monitoring rollout..."
for agent in intake faq complaint escalation; do
    echo "Checking $agent agent..."
    kubectl rollout status deployment/$RELEASE_NAME-$agent-agent -n $NAMESPACE --timeout=5m || {
        echo "❌ Rollout failed for $agent agent"
        exit 1
    }
done

# Step 6: Verify health
echo "🏥 Verifying agent health..."
sleep 10  # Give agents time to start

for agent in intake faq complaint escalation; do
    POD=$(kubectl get pod -n $NAMESPACE -l component=$agent-agent -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$POD" ]; then
        echo "Testing $agent agent health..."
        kubectl exec -n $NAMESPACE $POD -- wget -q -O- http://localhost:8080/health || {
            echo "⚠️  Health check failed for $agent"
        }
    fi
done

# Step 7: Show summary
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📈 Agent status:"
kubectl get pods -n $NAMESPACE -l app=$RELEASE_NAME -o wide

echo ""
echo "🔗 Services:"
kubectl get svc -n $NAMESPACE -l app=$RELEASE_NAME

echo ""
echo "📊 HPA status:"
kubectl get hpa -n $NAMESPACE -l app=$RELEASE_NAME 2>/dev/null || echo "No HPA configured"

echo ""
echo "💡 To check logs:"
echo "kubectl logs -n $NAMESPACE -l app=$RELEASE_NAME --tail=50 -f"

echo ""
echo "🔄 To rollback if needed:"
echo "argocd app rollback $RELEASE_NAME"