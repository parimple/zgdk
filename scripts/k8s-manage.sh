#!/bin/bash

# ZGDK Kubernetes Management Script

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default namespace
NAMESPACE="zgdk"

# Function to display usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status     - Show status of all pods"
    echo "  logs       - Show Discord bot logs"
    echo "  restart    - Restart Discord bot"
    echo "  update     - Update deployment with latest image"
    echo "  shell      - Open shell in Discord bot pod"
    echo "  config     - Show current config"
    echo "  secrets    - Update Discord token"
    echo ""
    exit 1
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl is not installed${NC}"
    exit 1
fi

# Main command handling
case "$1" in
    status)
        echo -e "${GREEN}=== ZGDK Kubernetes Status ===${NC}"
        kubectl get pods -n $NAMESPACE
        echo ""
        echo -e "${YELLOW}Services:${NC}"
        kubectl get svc -n $NAMESPACE
        ;;
        
    logs)
        echo -e "${GREEN}=== Discord Bot Logs ===${NC}"
        kubectl logs -l app=zgdk,component=discord-bot -n $NAMESPACE -f
        ;;
        
    restart)
        echo -e "${YELLOW}Restarting Discord bot...${NC}"
        kubectl rollout restart deployment/zgdk-discord-bot -n $NAMESPACE
        echo -e "${GREEN}Restart initiated. Check status with: $0 status${NC}"
        ;;
        
    update)
        echo -e "${YELLOW}Fetching latest image tag...${NC}"
        LATEST_TAG=$(curl -s "https://hub.docker.com/v2/repositories/ppyzel/zgdk/tags/?page_size=1&name=main-" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['results'][0]['name'] if d['results'] else 'latest')")
        echo "Latest tag: $LATEST_TAG"
        
        echo -e "${YELLOW}Updating deployment...${NC}"
        helm upgrade zgdk ./helm/zgdk \
            --namespace $NAMESPACE \
            --set image.tag="$LATEST_TAG" \
            --reuse-values
        
        echo -e "${GREEN}Update completed!${NC}"
        ;;
        
    shell)
        echo -e "${GREEN}Opening shell in Discord bot pod...${NC}"
        POD=$(kubectl get pod -l app=zgdk,component=discord-bot -n $NAMESPACE -o jsonpath="{.items[0].metadata.name}")
        kubectl exec -it $POD -n $NAMESPACE -- /bin/bash
        ;;
        
    config)
        echo -e "${GREEN}=== Current Config ===${NC}"
        kubectl get configmap zgdk-config -n $NAMESPACE -o yaml | grep -A 50 "config.yml: |" | head -50
        ;;
        
    secrets)
        echo -e "${YELLOW}Update Discord token${NC}"
        read -sp "Enter Discord Token: " TOKEN
        echo ""
        kubectl delete secret discord-secrets -n $NAMESPACE 2>/dev/null || true
        kubectl create secret generic discord-secrets \
            --from-literal=DISCORD_TOKEN="$TOKEN" \
            --namespace=$NAMESPACE
        echo -e "${GREEN}Token updated! Restart bot with: $0 restart${NC}"
        ;;
        
    *)
        usage
        ;;
esac