#!/bin/bash

echo "🚀 K3s Installation Script for ZGDK"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please run as normal user, not root${NC}"
   exit 1
fi

# Install K3s
echo "📦 Installing K3s..."
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

# Wait for K3s to be ready
echo ""
echo "⏳ Waiting for K3s to start..."
sleep 10

# Check K3s status
sudo systemctl status k3s --no-pager

# Setup kubeconfig
echo ""
echo "🔧 Setting up kubeconfig..."
mkdir -p $HOME/.kube
sudo cp /etc/rancher/k3s/k3s.yaml $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
export KUBECONFIG=$HOME/.kube/config

# Add to bashrc
echo 'export KUBECONFIG=$HOME/.kube/config' >> ~/.bashrc

# Install kubectl if not present
if ! command -v kubectl &> /dev/null; then
    echo ""
    echo "📦 Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
fi

# Install Helm
if ! command -v helm &> /dev/null; then
    echo ""
    echo "📦 Installing Helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Verify installation
echo ""
echo "✅ Verifying installation..."
kubectl version --short
helm version --short

# Check nodes
echo ""
echo "📊 Cluster status:"
kubectl get nodes
kubectl get pods --all-namespaces

# Create zgdk namespace
echo ""
echo "📦 Creating zgdk namespace..."
kubectl create namespace zgdk --dry-run=client -o yaml | kubectl apply -f -

# Install metrics server (optional but useful)
echo ""
echo "📊 Installing metrics server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch metrics server for K3s
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]' 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ K3s installation completed!${NC}"
echo ""
echo "🎯 Next steps:"
echo "1. Source your bashrc: source ~/.bashrc"
echo "2. Deploy ZGDK: ./scripts/deploy-to-k8s.sh"
echo ""
echo "📝 Useful commands:"
echo "- Check nodes: kubectl get nodes"
echo "- Check pods: kubectl get pods -A"
echo "- K3s status: sudo systemctl status k3s"
echo "- Uninstall: /usr/local/bin/k3s-uninstall.sh"