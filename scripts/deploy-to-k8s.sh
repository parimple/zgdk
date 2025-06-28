#!/bin/bash

echo "🚀 ZGDK Kubernetes Deployment Script"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
check_requirement() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✅ $1 is available${NC}"
        return 0
    fi
}

echo "📋 Checking requirements..."
check_requirement "kubectl" || exit 1
check_requirement "helm" || exit 1

# Check cluster connection
echo ""
echo "🔌 Checking Kubernetes cluster connection..."
if kubectl cluster-info &> /dev/null; then
    echo -e "${GREEN}✅ Connected to Kubernetes cluster${NC}"
    kubectl cluster-info | grep "Kubernetes" | head -1
else
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    echo "Please ensure your kubeconfig is set up correctly"
    exit 1
fi

# Create namespace
echo ""
echo "📦 Creating namespace 'zgdk'..."
kubectl create namespace zgdk --dry-run=client -o yaml | kubectl apply -f -

# Create secrets
echo ""
echo "🔐 Creating secrets..."
echo "Please provide the following values:"

# Discord token
read -sp "Discord Bot Token (ZAGADKA_TOKEN): " DISCORD_TOKEN
echo ""

# Database credentials
read -p "PostgreSQL User [zagadka]: " PG_USER
PG_USER=${PG_USER:-zagadka}

read -sp "PostgreSQL Password: " PG_PASSWORD
echo ""

read -p "PostgreSQL Database [zagadka]: " PG_DB
PG_DB=${PG_DB:-zagadka}

# Gemini API
read -sp "Gemini API Key (optional, press Enter to skip): " GEMINI_API_KEY
echo ""

# Create Discord secret
kubectl create secret generic discord-secrets \
  --from-literal=DISCORD_TOKEN="$DISCORD_TOKEN" \
  --namespace=zgdk \
  --dry-run=client -o yaml | kubectl apply -f -

# Create PostgreSQL secret
kubectl create secret generic postgres-secrets \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --namespace=zgdk \
  --dry-run=client -o yaml | kubectl apply -f -

# Create AI secret if provided
if [ -n "$GEMINI_API_KEY" ]; then
    kubectl create secret generic ai-secrets \
      --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
      --namespace=zgdk \
      --dry-run=client -o yaml | kubectl apply -f -
fi

# Deploy PostgreSQL
echo ""
echo "🐘 Deploying PostgreSQL..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: zgdk
spec:
  ports:
  - port: 5432
    targetPort: 5432
  selector:
    app: postgres
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: zgdk
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_USER
          value: "$PG_USER"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secrets
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          value: "$PG_DB"
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
EOF

# Deploy Redis
echo ""
echo "🔴 Deploying Redis..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: zgdk
spec:
  ports:
  - port: 6379
    targetPort: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: zgdk
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
EOF

# Wait for database to be ready
echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n zgdk --timeout=120s

# Update Helm values with current image tag
echo ""
echo "📝 Getting latest image tag from Docker Hub..."
LATEST_TAG=$(curl -s "https://hub.docker.com/v2/repositories/ppyzel/zgdk/tags/?page_size=1&name=main-" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['results'][0]['name'] if d['results'] else 'latest')")
echo "Latest tag: $LATEST_TAG"

# Deploy with Helm
echo ""
echo "⎈ Deploying ZGDK with Helm..."
helm upgrade --install zgdk ./helm/zgdk \
  --namespace zgdk \
  --set image.tag="$LATEST_TAG" \
  --set postgresql.host=postgres-service \
  --set postgresql.user="$PG_USER" \
  --set postgresql.database="$PG_DB" \
  --set redis.host=redis-service \
  --wait

# Check deployment status
echo ""
echo "📊 Checking deployment status..."
kubectl get pods -n zgdk

echo ""
echo "🎯 Next steps:"
echo "1. Check logs: kubectl logs -n zgdk -l app=zgdk -f"
echo "2. Check health: kubectl get pods -n zgdk -w"
echo "3. Install ArgoCD apps: ./scripts/argocd-setup.sh"
echo ""
echo "✅ Deployment script completed!"